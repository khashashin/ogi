from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ogi.api.dependencies import (
    get_plugin_engine,
    get_redis,
    get_rq_queue,
    get_transform_engine,
)
from ogi.config import settings
from ogi.models import AuditLogCreate, Entity, TransformJobMessage, TransformRun, TransformStatus
from ogi.models.edge import EdgeCreate
from ogi.store.api_key_store import ApiKeyStore
from ogi.store.audit_log_store import AuditLogStore
from ogi.store.edge_store import EdgeStore
from ogi.store.entity_store import EntityStore
from ogi.store.project_store import ProjectStore
from ogi.store.transform_run_store import TransformRunStore
from ogi.store.transform_settings_store import TransformSettingsStore
from ogi.store.user_plugin_preference_store import UserPluginPreferenceStore
from ogi.transforms.base import TransformConfig, TransformSetting

logger = logging.getLogger(__name__)


@dataclass
class PreparedTransform:
    transform_name: str
    project_id: UUID
    user_id: UUID
    entity: Entity
    transform: object
    plugin_name: str | None
    plugin_tier: str | None
    config_payload: TransformConfig
    injected_services: list[str]


def managed_api_key_names(transform: object) -> set[str]:
    return {
        s.name
        for s in getattr(transform, "settings", [])
        if isinstance(s, TransformSetting) and s.name.endswith("_api_key")
    }


def strip_managed_api_key_settings(transform: object, values: dict[str, str]) -> dict[str, str]:
    blocked = managed_api_key_names(transform)
    return {key: value for key, value in values.items() if key not in blocked}


def reject_managed_api_key_settings(transform: object, values: dict[str, str]) -> None:
    blocked = managed_api_key_names(transform)
    attempted = sorted(key for key in values if key in blocked)
    if attempted:
        raise HTTPException(
            status_code=400,
            detail=(
                f"API key settings must be configured in API Keys, not transform settings: "
                f"{', '.join(attempted)}"
            ),
        )


def _base_default_settings(transform: object) -> dict[str, str]:
    return {
        s.name: s.default
        for s in transform.effective_settings()
        if isinstance(s, TransformSetting) and s.default
    }


def _normalize_bool(raw: str) -> str | None:
    normalized = raw.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return "true"
    if normalized in {"false", "0", "no", "off"}:
        return "false"
    return None


def sanitize_transform_settings(
    transform: object,
    incoming: dict[str, str],
) -> dict[str, str]:
    allowed: dict[str, TransformSetting] = {
        s.name: s
        for s in transform.effective_settings()
        if isinstance(s, TransformSetting)
    }
    sanitized: dict[str, str] = {}
    for key, raw_value in incoming.items():
        setting = allowed.get(key)
        if setting is None:
            continue
        value = str(raw_value).strip()
        if setting.field_type in {"string", "secret"}:
            if setting.pattern and not re.match(setting.pattern, value):
                raise HTTPException(status_code=400, detail=f"Invalid value for setting '{key}'")
            if len(value) > 2000:
                raise HTTPException(status_code=400, detail=f"Value too long for setting '{key}'")
            sanitized[key] = value
        elif setting.field_type == "boolean":
            norm = _normalize_bool(value)
            if norm is None:
                raise HTTPException(status_code=400, detail=f"Invalid boolean for setting '{key}'")
            sanitized[key] = norm
        elif setting.field_type == "integer":
            try:
                parsed = int(value)
            except Exception:
                raise HTTPException(status_code=400, detail=f"Invalid integer for setting '{key}'")
            if setting.min_value is not None and parsed < int(setting.min_value):
                raise HTTPException(status_code=400, detail=f"Setting '{key}' is below minimum")
            if setting.max_value is not None and parsed > int(setting.max_value):
                raise HTTPException(status_code=400, detail=f"Setting '{key}' is above maximum")
            sanitized[key] = str(parsed)
        elif setting.field_type == "number":
            try:
                parsed_num = float(value)
            except Exception:
                raise HTTPException(status_code=400, detail=f"Invalid number for setting '{key}'")
            if setting.min_value is not None and parsed_num < setting.min_value:
                raise HTTPException(status_code=400, detail=f"Setting '{key}' is below minimum")
            if setting.max_value is not None and parsed_num > setting.max_value:
                raise HTTPException(status_code=400, detail=f"Setting '{key}' is above maximum")
            sanitized[key] = str(parsed_num)
        elif setting.field_type == "select":
            if setting.options and value not in setting.options:
                raise HTTPException(status_code=400, detail=f"Invalid option for setting '{key}'")
            sanitized[key] = value
        else:
            sanitized[key] = value
    return sanitized


async def resolve_transform_settings(
    transform: object,
    transform_name: str,
    user_id: UUID,
    store: TransformSettingsStore,
) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str]]:
    defaults = _base_default_settings(transform)
    global_settings = strip_managed_api_key_settings(transform, await store.get_global(transform_name))
    user_settings = strip_managed_api_key_settings(transform, await store.get_user(user_id, transform_name))
    resolved = {**defaults, **global_settings, **user_settings}
    return defaults, global_settings, user_settings, sanitize_transform_settings(transform, resolved)


def _service_allowed_for_api_key_injection(service_name: str) -> tuple[bool, str | None]:
    allowlist = {item.strip().lower() for item in settings.api_key_service_allowlist if item.strip()}
    blocklist = {item.strip().lower() for item in settings.api_key_service_blocklist if item.strip()}
    normalized = service_name.strip().lower()

    if normalized in blocklist:
        return False, f"Stored API key injection is blocked for service '{service_name}'"
    if allowlist and normalized not in allowlist:
        return False, f"Stored API key injection is not allowed for service '{service_name}'"
    return True, None


def _plugin_allowed_for_api_key_injection(
    plugin_name: str | None,
    plugin_tier: str | None,
) -> tuple[bool, str | None]:
    if not plugin_name:
        return True, None

    tier = (plugin_tier or "community").strip().lower()
    if not settings.api_key_injection_allow_community_plugins and tier == "community":
        return False, f"Stored API key injection is disabled for community plugins ('{plugin_name}')"

    if settings.api_key_injection_trusted_tiers_only:
        allowed_tiers = {
            item.strip().lower()
            for item in settings.api_key_injection_allowed_tiers
            if item.strip()
        }
        if tier not in allowed_tiers:
            return False, (
                f"Stored API key injection is restricted to trusted plugin tiers "
                f"({sorted(allowed_tiers)}); '{plugin_name}' is '{tier}'"
            )
    return True, None


class TransformExecutionService:
    def __init__(
        self,
        *,
        queue_getter=None,
        redis_getter=None,
    ) -> None:
        self._queue_getter = queue_getter or get_rq_queue
        self._redis_getter = redis_getter or get_redis

    async def validate_and_prepare(
        self,
        *,
        transform_name: str,
        entity_id: UUID,
        project_id: UUID,
        user_id: UUID,
        config_overrides: dict[str, str],
        session: AsyncSession,
    ) -> PreparedTransform:
        project_store = ProjectStore(session)
        entity_store = EntityStore(session)
        preferences = UserPluginPreferenceStore(session)
        api_key_store = ApiKeyStore(session)
        settings_store = TransformSettingsStore(session)

        role = await project_store.get_member_role(project_id, user_id)
        if role not in ("owner", "editor"):
            raise HTTPException(status_code=403, detail="Project editor access required")

        entity = await entity_store.get(entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="Entity not found")
        if entity.project_id != project_id:
            raise HTTPException(status_code=400, detail="Entity does not belong to the project")

        transform_engine = get_transform_engine()
        transform = transform_engine.get_transform(transform_name)
        if transform is None:
            raise HTTPException(status_code=400, detail=f"Transform '{transform_name}' not found")

        plugin_name = get_plugin_engine().get_plugin_for_transform(transform_name)
        if plugin_name and not await preferences.is_enabled(user_id, plugin_name, default=True):
            raise HTTPException(status_code=403, detail=f"Plugin '{plugin_name}' is disabled for this user")

        if not transform.can_run_on(entity):
            raise HTTPException(
                status_code=400,
                detail=f"Transform '{transform_name}' cannot run on entity type '{entity.type.value}'",
            )

        _defaults, _global_settings, _user_settings, resolved = await resolve_transform_settings(
            transform,
            transform_name,
            user_id,
            settings_store,
        )
        merged_settings = {
            **resolved,
            **sanitize_transform_settings(transform, config_overrides),
        }

        plugin = get_plugin_engine().get_plugin(plugin_name) if plugin_name else None
        plugin_tier = plugin.verification_tier if plugin is not None else None
        injected_services: list[str] = []

        for setting in getattr(transform, "settings", []):
            if not getattr(setting, "required", False):
                continue
            setting_name = getattr(setting, "name", "")
            if merged_settings.get(setting_name):
                continue
            if setting_name.endswith("_api_key"):
                service_name = setting_name.removesuffix("_api_key")
                if service_name:
                    service_allowed, service_error = _service_allowed_for_api_key_injection(service_name)
                    if not service_allowed:
                        raise HTTPException(status_code=403, detail=service_error)
                    plugin_allowed, plugin_error = _plugin_allowed_for_api_key_injection(
                        plugin_name,
                        plugin_tier,
                    )
                    if not plugin_allowed:
                        raise HTTPException(status_code=403, detail=plugin_error)
                    stored = await api_key_store.get_key(user_id, service_name)
                    if stored:
                        merged_settings[setting_name] = stored
                        injected_services.append(service_name)
            if getattr(setting, "required", False) and not merged_settings.get(setting_name):
                raise HTTPException(status_code=400, detail=f"Missing required setting '{setting_name}'")

        return PreparedTransform(
            transform_name=transform_name,
            project_id=project_id,
            user_id=user_id,
            entity=entity,
            transform=transform,
            plugin_name=plugin_name,
            plugin_tier=plugin_tier,
            config_payload=TransformConfig(settings=merged_settings),
            injected_services=injected_services,
        )

    async def execute_enqueued(
        self,
        *,
        prepared: PreparedTransform,
        session: AsyncSession,
    ) -> TransformRun:
        run_store = TransformRunStore(session)
        audit_store = AuditLogStore(session)
        run = TransformRun(
            project_id=prepared.project_id,
            transform_name=prepared.transform_name,
            input_entity_id=prepared.entity.id,
            status=TransformStatus.PENDING,
        )
        await run_store.save(run)

        for service_name in prepared.injected_services:
            await audit_store.create(
                prepared.project_id,
                prepared.user_id,
                AuditLogCreate(
                    action="transform.api_key_injected",
                    resource_type="transform",
                    resource_id=prepared.transform_name,
                    details={
                        "transform_name": prepared.transform_name,
                        "run_id": str(run.id),
                        "input_entity_id": str(prepared.entity.id),
                        "plugin_name": prepared.plugin_name,
                        "plugin_verification_tier": prepared.plugin_tier,
                        "service_name": service_name,
                        "injection_source": "stored_api_key",
                    },
                ),
            )

        queue = self._queue_getter()
        if queue is None:
            raise HTTPException(status_code=503, detail="Job queue not available — Redis may be down")

        try:
            from ogi.worker.transform_job import execute_transform

            queue.enqueue(
                execute_transform,
                str(run.id),
                prepared.transform_name,
                prepared.entity.model_dump(mode="json"),
                str(prepared.project_id),
                prepared.config_payload.model_dump(mode="json"),
                job_id=str(run.id),
                job_timeout=settings.transform_timeout,
            )
        except Exception:
            logger.exception("Failed to enqueue transform job %s", run.id)
            raise HTTPException(status_code=503, detail="Failed to enqueue transform job — Redis may be unavailable")

        redis_conn = self._redis_getter()
        if redis_conn is not None:
            redis_conn.publish(
                f"ogi:transform_events:{prepared.project_id}",
                TransformJobMessage(
                    type="job_submitted",
                    job_id=run.id,
                    project_id=prepared.project_id,
                    transform_name=prepared.transform_name,
                    input_entity_id=prepared.entity.id,
                    timestamp=datetime.now(timezone.utc),
                ).model_dump_json(),
            )
        return run

    async def execute_direct(
        self,
        *,
        prepared: PreparedTransform,
        session: AsyncSession,
    ) -> tuple[TransformRun, dict]:
        run_store = TransformRunStore(session)
        entity_store = EntityStore(session)
        edge_store = EdgeStore(session)
        audit_store = AuditLogStore(session)

        run = TransformRun(
            project_id=prepared.project_id,
            transform_name=prepared.transform_name,
            input_entity_id=prepared.entity.id,
            status=TransformStatus.PENDING,
        )
        await run_store.save(run)

        for service_name in prepared.injected_services:
            await audit_store.create(
                prepared.project_id,
                prepared.user_id,
                AuditLogCreate(
                    action="transform.api_key_injected",
                    resource_type="transform",
                    resource_id=prepared.transform_name,
                    details={
                        "transform_name": prepared.transform_name,
                        "run_id": str(run.id),
                        "input_entity_id": str(prepared.entity.id),
                        "plugin_name": prepared.plugin_name,
                        "plugin_verification_tier": prepared.plugin_tier,
                        "service_name": service_name,
                        "injection_source": "stored_api_key",
                    },
                ),
            )

        redis_conn = self._redis_getter()
        if redis_conn is not None:
            redis_conn.publish(
                f"ogi:transform_events:{prepared.project_id}",
                TransformJobMessage(
                    type="job_submitted",
                    job_id=run.id,
                    project_id=prepared.project_id,
                    transform_name=prepared.transform_name,
                    input_entity_id=prepared.entity.id,
                    timestamp=datetime.now(timezone.utc),
                ).model_dump_json(),
            )

        run.status = TransformStatus.RUNNING
        await run_store.save(run)
        if redis_conn is not None:
            redis_conn.publish(
                f"ogi:transform_events:{prepared.project_id}",
                TransformJobMessage(
                    type="job_started",
                    job_id=run.id,
                    project_id=prepared.project_id,
                    transform_name=prepared.transform_name,
                    input_entity_id=prepared.entity.id,
                    timestamp=datetime.now(timezone.utc),
                ).model_dump_json(),
            )

        try:
            result = await asyncio.wait_for(
                prepared.transform.run(prepared.entity, prepared.config_payload),
                timeout=settings.transform_timeout,
            )

            id_map: dict[UUID, UUID] = {}
            for new_entity in result.entities:
                saved = await entity_store.save(prepared.project_id, new_entity)
                id_map[new_entity.id] = saved.id

            for new_edge in result.edges:
                actual_source = id_map.get(new_edge.source_id, new_edge.source_id)
                actual_target = id_map.get(new_edge.target_id, new_edge.target_id)
                edge_data = EdgeCreate(
                    source_id=actual_source,
                    target_id=actual_target,
                    label=new_edge.label,
                    weight=new_edge.weight,
                    properties=new_edge.properties,
                    bidirectional=new_edge.bidirectional,
                    source_transform=new_edge.source_transform,
                )
                try:
                    await edge_store.create(prepared.project_id, edge_data)
                except Exception:
                    pass

            for entity_out in result.entities:
                entity_out.id = id_map.get(entity_out.id, entity_out.id)
                entity_out.project_id = prepared.project_id
            for edge in result.edges:
                edge.source_id = id_map.get(edge.source_id, edge.source_id)
                edge.target_id = id_map.get(edge.target_id, edge.target_id)

            result_dict = result.model_dump(mode="json")
            run.status = TransformStatus.COMPLETED
            run.result = result_dict
            run.completed_at = datetime.now(timezone.utc)
            await run_store.save(run)
            if redis_conn is not None:
                redis_conn.publish(
                    f"ogi:transform_events:{prepared.project_id}",
                    TransformJobMessage(
                        type="job_completed",
                        job_id=run.id,
                        project_id=prepared.project_id,
                        transform_name=prepared.transform_name,
                        input_entity_id=prepared.entity.id,
                        result=result_dict,
                        timestamp=datetime.now(timezone.utc),
                    ).model_dump_json(),
                )
            return run, result_dict
        except Exception as exc:
            logger.exception("Direct transform execution failed for %s", run.id)
            run.status = TransformStatus.FAILED
            run.error = str(exc)
            run.completed_at = datetime.now(timezone.utc)
            await run_store.save(run)
            if redis_conn is not None:
                redis_conn.publish(
                    f"ogi:transform_events:{prepared.project_id}",
                    TransformJobMessage(
                        type="job_failed",
                        job_id=run.id,
                        project_id=prepared.project_id,
                        transform_name=prepared.transform_name,
                        input_entity_id=prepared.entity.id,
                        error=str(exc),
                        timestamp=datetime.now(timezone.utc),
                    ).model_dump_json(),
                )
            raise
