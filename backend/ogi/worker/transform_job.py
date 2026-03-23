"""RQ job function for executing transforms in a worker process.

This runs in a **separate process** from FastAPI, so it must initialise its own
DB connection, TransformEngine, and PluginEngine.  Results are persisted to the
database and a completion event is published to Redis pub/sub so the FastAPI
WebSocket manager can broadcast to connected clients.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from redis import Redis

from ogi.config import settings
from ogi.db.database import init_db, close_db, get_session
from ogi.engine.transform_engine import TransformEngine
from ogi.models import (
    Entity,
    TransformResult,
    TransformRun,
    TransformStatus,
    TransformJobMessage,
)
from ogi.models.edge import EdgeCreate
from ogi.transforms.base import TransformConfig
from ogi.store.entity_store import EntityStore
from ogi.store.edge_store import EdgeStore
from ogi.store.transform_run_store import TransformRunStore

logger = logging.getLogger("ogi.worker")

# Module-level singletons, lazily initialised once per worker process.
_engine: TransformEngine | None = None


def _get_transform_engine() -> TransformEngine:
    """Lazily build and cache a TransformEngine for this worker process."""
    global _engine
    if _engine is None:
        _engine = TransformEngine()
        _engine.auto_discover()
        _engine.load_plugins(settings.plugin_dirs)
    return _engine


def _publish_event(redis_conn: Redis, msg: TransformJobMessage) -> None:  # type: ignore[type-arg]
    """Publish a TransformJobMessage to the project-specific Redis channel."""
    channel = f"ogi:transform_events:{msg.project_id}"
    redis_conn.publish(channel, msg.model_dump_json())


async def _run_transform_async(
    run_id: str,
    transform_name: str,
    entity_data: dict,
    project_id: str,
    config_data: dict,
) -> dict:
    """Async implementation that does the actual work."""

    await init_db()

    redis_conn = Redis.from_url(settings.redis_url, decode_responses=True)
    pid = UUID(project_id)
    rid = UUID(run_id)

    try:
        engine = _get_transform_engine()

        # Deserialise inputs
        entity = Entity.model_validate(entity_data)
        config = TransformConfig.model_validate(config_data)

        transform = engine.get_transform(transform_name)
        if transform is None:
            raise ValueError(f"Transform '{transform_name}' not found")

        # Publish "job_started"
        _publish_event(redis_conn, TransformJobMessage(
            type="job_started",
            job_id=rid,
            project_id=pid,
            transform_name=transform_name,
            input_entity_id=entity.id,
            timestamp=datetime.now(timezone.utc),
        ))

        # Update run to RUNNING
        async for session in get_session():
            run_store = TransformRunStore(session)
            run = await run_store.get(rid)
            if run:
                run.status = TransformStatus.RUNNING
                await run_store.save(run)
            break

        # Execute the transform (the interface that plugin authors implement)
        result = await transform.run(entity, config)

        # Persist entities + edges, deduplicating
        async for session in get_session():
            es = EntityStore(session)
            edge_s = EdgeStore(session)
            run_store = TransformRunStore(session)

            id_map: dict[UUID, UUID] = {}
            for new_entity in result.entities:
                saved = await es.save(pid, new_entity)
                id_map[new_entity.id] = saved.id

            for new_edge in result.edges:
                actual_source = id_map.get(new_edge.source_id, new_edge.source_id)
                actual_target = id_map.get(new_edge.target_id, new_edge.target_id)
                edge_data = EdgeCreate(
                    source_id=actual_source,
                    target_id=actual_target,
                    label=new_edge.label,
                    source_transform=new_edge.source_transform,
                )
                try:
                    await edge_s.create(pid, edge_data)
                except Exception:
                    pass  # skip duplicates

            # Remap entity IDs in result for the frontend
            result.entities = [
                Entity.model_validate({**e.model_dump(), "id": str(id_map.get(e.id, e.id))})
                for e in result.entities
            ]
            for edge in result.edges:
                edge.source_id = id_map.get(edge.source_id, edge.source_id)
                edge.target_id = id_map.get(edge.target_id, edge.target_id)

            result_dict = result.model_dump(mode="json")

            # Update the TransformRun record
            run = await run_store.get(rid)
            if run:
                run.status = TransformStatus.COMPLETED
                run.result = result_dict
                run.completed_at = datetime.now(timezone.utc)
                await run_store.save(run)

            break

        # Publish "job_completed"
        _publish_event(redis_conn, TransformJobMessage(
            type="job_completed",
            job_id=rid,
            project_id=pid,
            transform_name=transform_name,
            input_entity_id=entity.id,
            result=result_dict,
            timestamp=datetime.now(timezone.utc),
        ))

        return result_dict

    except Exception as exc:
        logger.exception("Transform job %s failed", run_id)

        # Mark run as FAILED in DB
        try:
            async for session in get_session():
                run_store = TransformRunStore(session)
                run = await run_store.get(rid)
                if run:
                    run.status = TransformStatus.FAILED
                    run.error = str(exc)
                    run.completed_at = datetime.now(timezone.utc)
                    await run_store.save(run)
                break
        except Exception:
            logger.exception("Failed to update run status in DB")

        # Publish "job_failed"
        _publish_event(redis_conn, TransformJobMessage(
            type="job_failed",
            job_id=rid,
            project_id=pid,
            transform_name=transform_name,
            input_entity_id=entity.id,
            error=str(exc),
            timestamp=datetime.now(timezone.utc),
        ))

        raise

    finally:
        redis_conn.close()
        await close_db()


def execute_transform(
    run_id: str,
    transform_name: str,
    entity_data: dict,
    project_id: str,
    config_data: dict,
) -> dict:
    """Synchronous entry point called by RQ.

    RQ workers are synchronous, so we bootstrap an event loop to run the async
    transform pipeline.
    """
    return asyncio.run(
        _run_transform_async(run_id, transform_name, entity_data, project_id, config_data)
    )
