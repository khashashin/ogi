"""WebSocket endpoint for real-time transform job notifications.

Clients connect per-project and receive ``TransformJobMessage`` events as
transforms progress through the RQ pipeline.  A background asyncio task
subscribes to Redis pub/sub and bridges messages to connected WebSockets.
"""

from __future__ import annotations

import asyncio
import json
import logging
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from ogi.config import settings
from ogi.models import UserProfile

logger = logging.getLogger("ogi.ws")

router = APIRouter(prefix="/ws", tags=["websocket"])


class ConnectionManager:
    """Track active WebSocket connections grouped by project."""

    def __init__(self) -> None:
        self._connections: dict[UUID, list[WebSocket]] = {}

    async def connect(self, project_id: UUID, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.setdefault(project_id, []).append(ws)
        logger.info("WS connected for project %s (total: %d)", project_id, len(self._connections[project_id]))

    def disconnect(self, project_id: UUID, ws: WebSocket) -> None:
        conns = self._connections.get(project_id)
        if conns and ws in conns:
            conns.remove(ws)
            if not conns:
                del self._connections[project_id]

    async def broadcast_to_project(self, project_id: UUID, message: str) -> None:
        """Send a JSON string to all connections for a project, cleaning up dead ones."""
        conns = self._connections.get(project_id)
        if not conns:
            return
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(project_id, ws)


ws_manager = ConnectionManager()


async def redis_pubsub_listener() -> None:
    """Background task: subscribe to Redis pub/sub and broadcast to WebSocket clients.

    Subscribes to ``ogi:transform_events:*`` pattern channels.  Each message is
    forwarded verbatim to the matching project's WebSocket connections.
    """
    import redis.asyncio as aioredis

    conn = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = conn.pubsub()
    await pubsub.psubscribe("ogi:transform_events:*")
    logger.info("Redis pub/sub listener started")

    try:
        async for raw_message in pubsub.listen():
            if raw_message["type"] != "pmessage":
                continue
            channel: str = raw_message["channel"]
            data: str = raw_message["data"]

            # Channel format: ogi:transform_events:<project_id>
            parts = channel.split(":")
            if len(parts) < 3:
                continue
            try:
                project_id = UUID(parts[2])
            except ValueError:
                continue

            await ws_manager.broadcast_to_project(project_id, data)
    except asyncio.CancelledError:
        logger.info("Redis pub/sub listener cancelled")
    except Exception:
        logger.exception("Redis pub/sub listener error")
    finally:
        await pubsub.punsubscribe("ogi:transform_events:*")
        await conn.aclose()


async def _resolve_ws_user(token: str | None) -> UserProfile | None:
    """Resolve the websocket caller to a user profile."""
    # Local mode: behave like HTTP auth dependency and allow anonymous profile.
    if not settings.supabase_url or not settings.supabase_anon_key:
        return UserProfile(
            id=UUID("00000000-0000-0000-0000-000000000000"),
            email="local@localhost",
        )

    if not token:
        return None

    try:
        from ogi.api.auth import get_supabase_client
        from ogi.db.database import get_session

        client = get_supabase_client()
        if not client:
            return None
        resp = client.auth.get_user(token)
        if resp is None or resp.user is None:
            return None

        user_id = UUID(str(resp.user.id))
        email = str(resp.user.email or "")

        async for session in get_session():
            profile = await session.get(UserProfile, user_id)
            if not profile:
                profile = UserProfile(id=user_id, email=email)
                profile = await session.merge(profile)
                try:
                    await session.commit()
                except Exception:
                    await session.rollback()
                    profile = await session.get(UserProfile, user_id)
                    if not profile:
                        return None
            elif profile.email != email:
                profile.email = email
                session.add(profile)
                await session.commit()
            return profile
    except Exception:
        return None
    return None


async def _get_project_role(project_id: UUID, user_id: UUID) -> str | None:
    from ogi.db.database import get_session
    from ogi.store.project_store import ProjectStore

    async for session in get_session():
        store = ProjectStore(session)
        return await store.get_member_role(project_id, user_id)
    return None


@router.websocket("/transforms/{project_id}")
async def ws_transforms(
    ws: WebSocket,
    project_id: UUID,
    token: str | None = Query(default=None),
) -> None:
    """WebSocket endpoint for transform job events on a project."""

    user = await _resolve_ws_user(token)
    if user is None:
        await ws.close(code=4001, reason="Unauthorized")
        return

    role = await _get_project_role(project_id, user.id)
    if role not in ("owner", "editor", "viewer"):
        await ws.close(code=4003, reason="Forbidden")
        return

    await ws_manager.connect(project_id, ws)

    try:
        while True:
            text = await ws.receive_text()
            try:
                msg = json.loads(text)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")

            if msg_type == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))

            elif msg_type == "cancel":
                job_id = msg.get("job_id")
                if job_id:
                    await _handle_cancel(project_id, user.id, job_id)

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket error for project %s", project_id)
    finally:
        ws_manager.disconnect(project_id, ws)


async def _handle_cancel(project_id: UUID, user_id: UUID, job_id: str) -> None:
    """Cancel an RQ job and publish cancellation event."""
    from ogi.api.dependencies import get_redis
    from ogi.models import TransformStatus, TransformJobMessage
    from ogi.db.database import get_session
    from ogi.store.project_store import ProjectStore
    from ogi.store.transform_run_store import TransformRunStore
    from datetime import datetime, timezone
    from rq.job import Job

    redis_conn = get_redis()
    if redis_conn is None:
        return

    try:
        run_id = UUID(job_id)
    except ValueError:
        logger.warning("Received invalid cancel job id: %s", job_id)
        return

    try:
        async for session in get_session():
            project_store = ProjectStore(session)
            run_store = TransformRunStore(session)
            run = await run_store.get(run_id)
            if run is None or run.project_id != project_id:
                break

            role = await project_store.get_member_role(project_id, user_id)
            if role not in ("owner", "editor"):
                break

            if run.status not in (TransformStatus.PENDING, TransformStatus.RUNNING):
                break

            try:
                rq_job = Job.fetch(job_id, connection=redis_conn)
                rq_job.cancel()
            except Exception:
                logger.warning("Could not cancel RQ job %s", job_id)

            run.status = TransformStatus.CANCELLED
            run.completed_at = datetime.now(timezone.utc)
            await run_store.save(run)

            # Publish cancellation event
            msg = TransformJobMessage(
                type="job_cancelled",
                job_id=run_id,
                project_id=project_id,
                transform_name=run.transform_name,
                input_entity_id=run.input_entity_id,
                timestamp=datetime.now(timezone.utc),
            )
            redis_conn.publish(
                f"ogi:transform_events:{project_id}",
                msg.model_dump_json(),
            )
            break
    except Exception:
        logger.exception("Failed to update cancelled run %s", job_id)
