from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ogi.config import settings
from ogi.models import (
    ENTITY_TYPE_DOCS,
    ENTITY_TYPE_META,
    EntityType,
    EntityTypeDocumentation,
    EntityTypeTransformRef,
    TransformDocumentation,
    TransformInfo,
    TransformRun,
    TransformStatus,
    TransformJobMessage,
    UserProfile,
)
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
from ogi.engine.transform_engine import _api_key_services
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


@router.get("/{name}/documentation", response_model=TransformDocumentation)
async def get_transform_documentation(
    name: str,
    current_user: UserProfile = Depends(get_current_user),
) -> TransformDocumentation:
    """Long-form docs for one transform, assembled from every source available.

    Class attributes win over the plugin manifest, which wins over nothing at
    all; the plugin README is returned alongside as supplementary material.
    """
    transform = get_transform_engine().get_transform(name)
    if transform is None:
        raise HTTPException(status_code=404, detail=f"Transform '{name}' not found")

    doc = TransformDocumentation(
        name=transform.name,
        display_name=transform.display_name,
        description=transform.description,
        long_description=getattr(transform, "long_description", "") or "",
        when_to_use=getattr(transform, "when_to_use", "") or "",
        limitations=getattr(transform, "limitations", "") or "",
        example_use_cases=list(getattr(transform, "example_use_cases", []) or []),
        input_types=transform.input_types,
        output_types=transform.output_types,
        category=transform.category,
        api_key_services=_api_key_services(transform),
        setting_names=[s.display_name or s.name for s in transform.effective_settings()],
    )

    plugin_engine = get_plugin_engine()
    plugin_name = plugin_engine.get_plugin_for_transform(transform.name)
    if plugin_name is None:
        return doc

    doc.source = "plugin"
    doc.plugin_name = plugin_name
    doc.readme = plugin_engine.get_plugin_readme(plugin_name)

    manifest_docs = plugin_engine.get_plugin_documentation(plugin_name)
    if manifest_docs is not None:
        doc.long_description = doc.long_description or manifest_docs.long_description
        doc.when_to_use = doc.when_to_use or manifest_docs.when_to_use
        doc.limitations = doc.limitations or manifest_docs.limitations
        doc.example_use_cases = doc.example_use_cases or manifest_docs.example_use_cases

    plugin = plugin_engine.get_plugin(plugin_name)
    if plugin is not None:
        doc.plugin_version = plugin.version
        doc.plugin_author = plugin.author
        doc.plugin_verification_tier = plugin.verification_tier or "community"
        doc.plugin_homepage = plugin.homepage
        doc.plugin_repository = plugin.repository

    return doc


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


@router.get("/entity-types/{entity_type}/documentation", response_model=EntityTypeDocumentation)
async def get_entity_type_documentation(
    entity_type: EntityType,
    current_user: UserProfile = Depends(get_current_user),
    preferences: UserPluginPreferenceStore = Depends(get_user_plugin_preference_store),
) -> EntityTypeDocumentation:
    """Explain an entity type and list the transforms wired to it.

    ``consumed_by`` is what you can run on one; ``produced_by`` is how one gets
    discovered in the first place.
    """
    meta = ENTITY_TYPE_META.get(entity_type, {})
    docs = ENTITY_TYPE_DOCS.get(entity_type, {})

    engine = get_transform_engine()
    enabled_by_plugin = await preferences.list_for_user(current_user.id)
    plugin_engine = get_plugin_engine()

    def _ref(transform: TransformInfo) -> EntityTypeTransformRef:
        return EntityTypeTransformRef(
            name=transform.name,
            display_name=transform.display_name,
            description=transform.description,
            category=transform.category,
            api_key_services=transform.api_key_services,
            plugin_name=plugin_engine.get_plugin_for_transform(transform.name),
        )

    consumed_by: list[EntityTypeTransformRef] = []
    produced_by: list[EntityTypeTransformRef] = []
    for transform in engine.list_transforms():
        if not _transform_visible_to_user(transform.name, enabled_by_plugin):
            continue
        if entity_type in transform.input_types:
            consumed_by.append(_ref(transform))
        if entity_type in transform.output_types:
            produced_by.append(_ref(transform))

    sort_key = lambda ref: ref.display_name.lower()  # noqa: E731
    return EntityTypeDocumentation(
        type=entity_type,
        category=str(meta.get("category", "")),
        icon=str(meta.get("icon", "")),
        color=str(meta.get("color", "")),
        description=str(docs.get("description", "")),
        usage=str(docs.get("usage", "")),
        consumed_by=sorted(consumed_by, key=sort_key),
        produced_by=sorted(produced_by, key=sort_key),
    )


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
