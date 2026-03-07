from datetime import datetime, timezone
import logging
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ogi.config import settings
from ogi.models import AuditLogCreate, TransformInfo, TransformRun, TransformStatus, TransformJobMessage, UserProfile
from ogi.transforms.base import TransformConfig, TransformSetting
from ogi.api.auth import get_current_user, require_project_viewer, require_admin_user
from ogi.api.dependencies import (
    get_audit_log_store,
    get_transform_engine,
    get_entity_store,
    get_entity_registry,
    get_transform_run_store,
    get_project_store,
    get_rq_queue,
    get_redis,
    get_plugin_engine,
    get_user_plugin_preference_store,
    get_api_key_store,
    get_transform_settings_store,
)
from ogi.store.project_store import ProjectStore
from ogi.store.entity_store import EntityStore
from ogi.store.transform_run_store import TransformRunStore
from ogi.store.audit_log_store import AuditLogStore
from ogi.store.user_plugin_preference_store import UserPluginPreferenceStore
from ogi.store.api_key_store import ApiKeyStore
from ogi.store.transform_settings_store import TransformSettingsStore

router = APIRouter(prefix="/transforms", tags=["transforms"])
logger = logging.getLogger(__name__)


class RunTransformRequest(BaseModel):
    entity_id: UUID
    project_id: UUID
    config: TransformConfig = Field(default_factory=TransformConfig)


class SaveTransformSettingsRequest(BaseModel):
    settings: dict[str, str] = Field(default_factory=dict)


class TransformSettingsResponse(BaseModel):
    transform_name: str
    settings_schema: list[dict[str, object]]
    defaults: dict[str, str]
    global_settings: dict[str, str]
    user_settings: dict[str, str]
    resolved: dict[str, str]
    can_manage_global: bool


def _managed_api_key_names(transform: object) -> set[str]:
    return {
        s.name
        for s in getattr(transform, "settings", [])
        if isinstance(s, TransformSetting) and s.name.endswith("_api_key")
    }


def _strip_managed_api_key_settings(transform: object, values: dict[str, str]) -> dict[str, str]:
    blocked = _managed_api_key_names(transform)
    return {key: value for key, value in values.items() if key not in blocked}


def _reject_managed_api_key_settings(transform: object, values: dict[str, str]) -> None:
    blocked = _managed_api_key_names(transform)
    attempted = sorted(key for key in values if key in blocked)
    if attempted:
        raise HTTPException(
            status_code=400,
            detail=(
                f"API key settings must be configured in API Keys, not transform settings: "
                f"{', '.join(attempted)}"
            ),
        )


def _transform_visible_to_user(
    transform_name: str,
    plugin_enabled_map: dict[str, bool],
) -> bool:
    plugin_name = get_plugin_engine().get_plugin_for_transform(transform_name)
    if plugin_name is None:
        return True
    return plugin_enabled_map.get(plugin_name, True)


def _enrich_transform_info(transform: TransformInfo) -> TransformInfo:
    plugin_name = get_plugin_engine().get_plugin_for_transform(transform.name)
    if plugin_name is None:
        return transform

    plugin = get_plugin_engine().get_plugin(plugin_name)
    if plugin is None:
        return transform.model_copy(update={"plugin_name": plugin_name})

    return transform.model_copy(
        update={
            "plugin_name": plugin_name,
            "plugin_verification_tier": plugin.verification_tier or "community",
            "plugin_permissions": plugin.permissions or {},
            "plugin_source": plugin.source or "local",
        }
    )


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
        return False, (
            f"Stored API key injection is disabled for community plugins "
            f"('{plugin_name}')"
        )

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


def _base_default_settings(transform: object) -> dict[str, str]:
    return {
        s.name: s.default
        for s in getattr(transform, "settings", [])
        if isinstance(s, TransformSetting) and s.default
    }


def _normalize_bool(raw: str) -> str | None:
    normalized = raw.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return "true"
    if normalized in {"false", "0", "no", "off"}:
        return "false"
    return None


def _sanitize_settings(
    transform: object,
    incoming: dict[str, str],
) -> dict[str, str]:
    allowed: dict[str, TransformSetting] = {
        s.name: s
        for s in getattr(transform, "settings", [])
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


async def _resolve_settings(
    transform: object,
    transform_name: str,
    current_user: UserProfile,
    store: TransformSettingsStore,
) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str]]:
    defaults = _base_default_settings(transform)
    global_settings = _strip_managed_api_key_settings(transform, await store.get_global(transform_name))
    user_settings = _strip_managed_api_key_settings(transform, await store.get_user(current_user.id, transform_name))
    resolved = {**defaults, **global_settings, **user_settings}
    return defaults, global_settings, user_settings, _sanitize_settings(transform, resolved)


@router.get("", response_model=list[TransformInfo])
async def list_transforms(
    current_user: UserProfile = Depends(get_current_user),
    preferences: UserPluginPreferenceStore = Depends(get_user_plugin_preference_store),
) -> list[TransformInfo]:
    engine = get_transform_engine()
    all_transforms = engine.list_transforms()
    enabled_by_plugin = await preferences.list_for_user(current_user.id)
    return [
        _enrich_transform_info(transform)
        for transform in all_transforms
        if _transform_visible_to_user(transform.name, enabled_by_plugin)
    ]   


@router.get("/{name}/settings", response_model=TransformSettingsResponse)
async def get_transform_settings(
    name: str,
    current_user: UserProfile = Depends(get_current_user),
    store: TransformSettingsStore = Depends(get_transform_settings_store),
) -> TransformSettingsResponse:
    transform = get_transform_engine().get_transform(name)
    if transform is None:
        raise HTTPException(status_code=404, detail=f"Transform '{name}' not found")
    defaults, global_settings, user_settings, resolved = await _resolve_settings(
        transform, name, current_user, store
    )
    return TransformSettingsResponse(
        transform_name=name,
        settings_schema=[s.model_dump(mode="json") for s in getattr(transform, "settings", [])],
        defaults=defaults,
        global_settings=global_settings,
        user_settings=user_settings,
        resolved=resolved,
        can_manage_global=(
            (not settings.supabase_url or not settings.supabase_anon_key)
            or current_user.email.lower() in settings.get_admin_emails()
        ),
    )


@router.put("/{name}/settings/user", response_model=TransformSettingsResponse)
async def save_user_transform_settings(
    name: str,
    data: SaveTransformSettingsRequest,
    current_user: UserProfile = Depends(get_current_user),
    store: TransformSettingsStore = Depends(get_transform_settings_store),
) -> TransformSettingsResponse:
    transform = get_transform_engine().get_transform(name)
    if transform is None:
        raise HTTPException(status_code=404, detail=f"Transform '{name}' not found")
    sanitized = _sanitize_settings(transform, data.settings)
    _reject_managed_api_key_settings(transform, sanitized)
    await store.set_user(current_user.id, name, sanitized)
    defaults, global_settings, user_settings, resolved = await _resolve_settings(
        transform, name, current_user, store
    )
    return TransformSettingsResponse(
        transform_name=name,
        settings_schema=[s.model_dump(mode="json") for s in getattr(transform, "settings", [])],
        defaults=defaults,
        global_settings=global_settings,
        user_settings=user_settings,
        resolved=resolved,
        can_manage_global=(
            (not settings.supabase_url or not settings.supabase_anon_key)
            or current_user.email.lower() in settings.get_admin_emails()
        ),
    )


@router.put("/{name}/settings/global", response_model=TransformSettingsResponse)
async def save_global_transform_settings(
    name: str,
    data: SaveTransformSettingsRequest,
    current_user: UserProfile = Depends(get_current_user),
    _admin_user: UserProfile = Depends(require_admin_user),
    store: TransformSettingsStore = Depends(get_transform_settings_store),
) -> TransformSettingsResponse:
    transform = get_transform_engine().get_transform(name)
    if transform is None:
        raise HTTPException(status_code=404, detail=f"Transform '{name}' not found")
    sanitized = _sanitize_settings(transform, data.settings)
    _reject_managed_api_key_settings(transform, sanitized)
    await store.set_global(name, sanitized)
    defaults, global_settings, user_settings, resolved = await _resolve_settings(
        transform, name, current_user, store
    )
    return TransformSettingsResponse(
        transform_name=name,
        settings_schema=[s.model_dump(mode="json") for s in getattr(transform, "settings", [])],
        defaults=defaults,
        global_settings=global_settings,
        user_settings=user_settings,
        resolved=resolved,
        can_manage_global=True,
    )


@router.get("/entity-types")
async def list_entity_types(
    _current_user: UserProfile = Depends(get_current_user),
) -> list[dict[str, str]]:
    registry = get_entity_registry()
    return registry.list_types_dict()


@router.get("/for-entity/{entity_id}", response_model=list[TransformInfo])
async def list_transforms_for_entity(
    entity_id: UUID,
    current_user: UserProfile = Depends(get_current_user),
    entity_store: EntityStore = Depends(get_entity_store),
    preferences: UserPluginPreferenceStore = Depends(get_user_plugin_preference_store),
) -> list[TransformInfo]:
    entity = await entity_store.get(entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    engine = get_transform_engine()
    enabled_by_plugin = await preferences.list_for_user(current_user.id)
    return [
        _enrich_transform_info(transform)
        for transform in engine.list_for_entity(entity)
        if _transform_visible_to_user(transform.name, enabled_by_plugin)
    ]


@router.post("/{name}/run", response_model=TransformRun)
async def run_transform(
    name: str,
    request: RunTransformRequest,
    current_user: UserProfile = Depends(get_current_user),
    project_store: ProjectStore = Depends(get_project_store),
    entity_store: EntityStore = Depends(get_entity_store),
    run_store: TransformRunStore = Depends(get_transform_run_store),
    preferences: UserPluginPreferenceStore = Depends(get_user_plugin_preference_store),
    api_key_store: ApiKeyStore = Depends(get_api_key_store),
    settings_store: TransformSettingsStore = Depends(get_transform_settings_store),
    audit_store: AuditLogStore = Depends(get_audit_log_store),
) -> TransformRun:
    role = await project_store.get_member_role(request.project_id, current_user.id)
    if role not in ("owner", "editor"):
        raise HTTPException(status_code=403, detail="Project editor access required")

    entity = await entity_store.get(request.entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    transform_engine = get_transform_engine()
    transform = transform_engine.get_transform(name)
    if transform is None:
        raise HTTPException(status_code=400, detail=f"Transform '{name}' not found")

    plugin_name = get_plugin_engine().get_plugin_for_transform(name)
    if plugin_name and not await preferences.is_enabled(current_user.id, plugin_name, default=True):
        raise HTTPException(status_code=403, detail=f"Plugin '{plugin_name}' is disabled for this user")

    if not transform.can_run_on(entity):
        raise HTTPException(
            status_code=400,
            detail=f"Transform '{name}' cannot run on entity type '{entity.type.value}'",
        )

    defaults, global_settings, user_settings, resolved = await _resolve_settings(
        transform, name, current_user, settings_store
    )
    merged_settings = {
        **resolved,
        **_sanitize_settings(transform, request.config.settings),
    }

    plugin = get_plugin_engine().get_plugin(plugin_name) if plugin_name else None
    plugin_tier = plugin.verification_tier if plugin is not None else None
    injected_services: list[str] = []

    # Auto-inject required API keys when a setting follows "<service>_api_key".
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
                stored = await api_key_store.get_key(current_user.id, service_name)
                if stored:
                    merged_settings[setting_name] = stored
                    injected_services.append(service_name)
        if getattr(setting, "required", False) and not merged_settings.get(setting_name):
            raise HTTPException(status_code=400, detail=f"Missing required setting '{setting_name}'")

    config_payload = TransformConfig(settings=merged_settings)

    # Create a PENDING run record
    run = TransformRun(
        project_id=request.project_id,
        transform_name=name,
        input_entity_id=entity.id,
        status=TransformStatus.PENDING,
    )
    await run_store.save(run)

    for service_name in injected_services:
        await audit_store.create(
            request.project_id,
            current_user.id,
            AuditLogCreate(
                action="transform.api_key_injected",
                resource_type="transform",
                resource_id=name,
                details={
                    "transform_name": name,
                    "run_id": str(run.id),
                    "input_entity_id": str(entity.id),
                    "plugin_name": plugin_name,
                    "plugin_verification_tier": plugin_tier,
                    "service_name": service_name,
                    "injection_source": "stored_api_key",
                },
            ),
        )

    # Enqueue the job via RQ
    queue = get_rq_queue()
    if queue is None:
        raise HTTPException(status_code=503, detail="Job queue not available — Redis may be down")

    try:
        from ogi.worker.transform_job import execute_transform
        queue.enqueue(
            execute_transform,
            str(run.id),
            name,
            entity.model_dump(mode="json"),
            str(request.project_id),
            config_payload.model_dump(mode="json"),
            job_id=str(run.id),
            job_timeout=settings.transform_timeout,
        )
    except Exception:
        logger.exception("Failed to enqueue transform job %s", run.id)
        raise HTTPException(status_code=503, detail="Failed to enqueue transform job — Redis may be unavailable")

    # Publish "job_submitted" event so WS clients see it immediately
    redis_conn = get_redis()
    if redis_conn is not None:
        msg = TransformJobMessage(
            type="job_submitted",
            job_id=run.id,
            project_id=request.project_id,
            transform_name=name,
            input_entity_id=entity.id,
            timestamp=datetime.now(timezone.utc),
        )
        redis_conn.publish(
            f"ogi:transform_events:{request.project_id}",
            msg.model_dump_json(),
        )

    return run


@router.post("/runs/{run_id}/cancel")
async def cancel_transform(
    run_id: UUID,
    current_user: UserProfile = Depends(get_current_user),
    project_store: ProjectStore = Depends(get_project_store),
    run_store: TransformRunStore = Depends(get_transform_run_store),
) -> dict[str, str]:
    """Cancel a pending/running transform job."""
    run = await run_store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Transform run not found")

    role = await project_store.get_member_role(run.project_id, current_user.id)
    if role not in ("owner", "editor"):
        raise HTTPException(status_code=403, detail="Project editor access required")

    if run.status not in (TransformStatus.PENDING, TransformStatus.RUNNING):
        raise HTTPException(status_code=400, detail=f"Cannot cancel a {run.status.value} job")

    redis_conn = get_redis()

    # Cancel in RQ
    if redis_conn is not None:
        try:
            from rq.job import Job
            rq_job = Job.fetch(str(run_id), connection=redis_conn)
            rq_job.cancel()
        except Exception:
            pass  # job may have already finished

    # Update DB
    run.status = TransformStatus.CANCELLED
    run.completed_at = datetime.now(timezone.utc)
    await run_store.save(run)

    # Publish cancellation event
    if redis_conn is not None:
        msg = TransformJobMessage(
            type="job_cancelled",
            job_id=run.id,
            project_id=run.project_id,
            transform_name=run.transform_name,
            input_entity_id=run.input_entity_id,
            timestamp=datetime.now(timezone.utc),
        )
        redis_conn.publish(
            f"ogi:transform_events:{run.project_id}",
            msg.model_dump_json(),
        )

    return {"status": "cancelled", "run_id": str(run_id)}


@router.get("/runs/{run_id}", response_model=TransformRun)
async def get_run(
    run_id: UUID,
    current_user: UserProfile = Depends(get_current_user),
    project_store: ProjectStore = Depends(get_project_store),
    run_store: TransformRunStore = Depends(get_transform_run_store),
) -> TransformRun:
    # Try in-memory first, then DB.
    engine = get_transform_engine()
    run = engine.get_run(run_id)
    if run is None:
        run = await run_store.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Transform run not found")

    role = await project_store.get_member_role(run.project_id, current_user.id)
    if role not in ("owner", "editor", "viewer"):
        raise HTTPException(status_code=403, detail="Not authorized to access this project")

    return run


@router.get("/project/{project_id}/runs", response_model=list[TransformRun])
async def list_project_runs(
    project_id: UUID,
    _role: str = Depends(require_project_viewer),
    run_store: TransformRunStore = Depends(get_transform_run_store),
) -> list[TransformRun]:
    return await run_store.list_by_project(project_id)
