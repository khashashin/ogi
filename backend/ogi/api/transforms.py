from datetime import datetime, timezone
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ogi.config import settings
from ogi.models import TransformInfo, TransformRun, TransformResult, TransformStatus, TransformJobMessage, EdgeCreate, UserProfile
from ogi.transforms.base import TransformConfig
from ogi.api.auth import get_current_user, require_project_viewer
from ogi.api.dependencies import (
    get_transform_engine,
    get_entity_store,
    get_entity_registry,
    get_edge_store,
    get_graph_engine,
    get_transform_run_store,
    get_project_store,
    get_rq_queue,
    get_redis,
    get_plugin_engine,
    get_user_plugin_preference_store,
)
from ogi.store.project_store import ProjectStore
from ogi.store.entity_store import EntityStore
from ogi.store.edge_store import EdgeStore
from ogi.store.transform_run_store import TransformRunStore
from ogi.store.user_plugin_preference_store import UserPluginPreferenceStore

router = APIRouter(prefix="/transforms", tags=["transforms"])
logger = logging.getLogger(__name__)


class RunTransformRequest(BaseModel):
    entity_id: UUID
    project_id: UUID
    config: TransformConfig = Field(default_factory=TransformConfig)


def _transform_visible_to_user(
    transform_name: str,
    plugin_enabled_map: dict[str, bool],
) -> bool:
    plugin_name = get_plugin_engine().get_plugin_for_transform(transform_name)
    if plugin_name is None:
        return True
    return plugin_enabled_map.get(plugin_name, True)


@router.get("", response_model=list[TransformInfo])
async def list_transforms(
    current_user: UserProfile = Depends(get_current_user),
    preferences: UserPluginPreferenceStore = Depends(get_user_plugin_preference_store),
) -> list[TransformInfo]:
    engine = get_transform_engine()
    all_transforms = engine.list_transforms()
    enabled_by_plugin = await preferences.list_for_user(current_user.id)
    return [
        transform
        for transform in all_transforms
        if _transform_visible_to_user(transform.name, enabled_by_plugin)
    ]


@router.get("/entity-types")
async def list_entity_types(
    current_user: UserProfile = Depends(get_current_user),
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
        transform
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

    # Create a PENDING run record
    run = TransformRun(
        project_id=request.project_id,
        transform_name=name,
        input_entity_id=entity.id,
        status=TransformStatus.PENDING,
    )
    await run_store.save(run)

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
            request.config.model_dump(mode="json"),
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
    run_store: TransformRunStore = Depends(get_transform_run_store),
) -> dict[str, str]:
    """Cancel a pending/running transform job."""
    run = await run_store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Transform run not found")

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
    run_store: TransformRunStore = Depends(get_transform_run_store),
) -> TransformRun:
    # Try in-memory first, then DB
    engine = get_transform_engine()
    run = engine.get_run(run_id)
    if run is not None:
        return run
    run = await run_store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Transform run not found")
    return run


@router.get("/project/{project_id}/runs", response_model=list[TransformRun])
async def list_project_runs(
    project_id: UUID,
    role: str = Depends(require_project_viewer),
    current_user: UserProfile = Depends(get_current_user),
    run_store: TransformRunStore = Depends(get_transform_run_store),
) -> list[TransformRun]:
    return await run_store.list_by_project(project_id)
