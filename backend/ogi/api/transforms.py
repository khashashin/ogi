from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ogi.config import settings
from ogi.models import TransformInfo, TransformRun, TransformStatus, TransformJobMessage, UserProfile
from ogi.transforms.base import TransformConfig
from ogi.api.auth import get_current_user, require_project_viewer, require_admin_user
from ogi.api.dependencies import (
    get_transform_engine,
    get_entity_store,
    get_entity_registry,
    get_transform_run_store,
    get_project_store,
    get_rq_queue,
    get_redis,
    get_plugin_engine,
    get_user_plugin_preference_store,
    get_transform_settings_store,
)
from ogi.engine.transform_execution_service import (
    TransformExecutionService,
    reject_managed_api_key_settings,
    resolve_transform_settings,
    sanitize_transform_settings,
)
from ogi.store.project_store import ProjectStore
from ogi.store.entity_store import EntityStore
from ogi.store.transform_run_store import TransformRunStore
from ogi.store.user_plugin_preference_store import UserPluginPreferenceStore
from ogi.store.transform_settings_store import TransformSettingsStore

router = APIRouter(prefix="/transforms", tags=["transforms"])


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
    defaults, global_settings, user_settings, resolved = await resolve_transform_settings(
        transform, name, current_user.id, store
    )
    return TransformSettingsResponse(
        transform_name=name,
        settings_schema=[s.model_dump(mode="json") for s in transform.effective_settings()],
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
    sanitized = sanitize_transform_settings(transform, data.settings)
    reject_managed_api_key_settings(transform, sanitized)
    await store.set_user(current_user.id, name, sanitized)
    defaults, global_settings, user_settings, resolved = await resolve_transform_settings(
        transform, name, current_user.id, store
    )
    return TransformSettingsResponse(
        transform_name=name,
        settings_schema=[s.model_dump(mode="json") for s in transform.effective_settings()],
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
    sanitized = sanitize_transform_settings(transform, data.settings)
    reject_managed_api_key_settings(transform, sanitized)
    await store.set_global(name, sanitized)
    defaults, global_settings, user_settings, resolved = await resolve_transform_settings(
        transform, name, current_user.id, store
    )
    return TransformSettingsResponse(
        transform_name=name,
        settings_schema=[s.model_dump(mode="json") for s in transform.effective_settings()],
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
    entity_store: EntityStore = Depends(get_entity_store),
) -> TransformRun:
    service = TransformExecutionService(
        queue_getter=get_rq_queue,
        redis_getter=get_redis,
    )
    prepared = await service.validate_and_prepare(
        transform_name=name,
        entity_id=request.entity_id,
        project_id=request.project_id,
        user_id=current_user.id,
        config_overrides=request.config.settings,
        session=entity_store.session,
    )
    return await service.execute_enqueued(prepared=prepared, session=entity_store.session)


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
