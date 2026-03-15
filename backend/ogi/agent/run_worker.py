"""Entry point for starting the AI Investigator worker.

Usage:
    python -m ogi.agent.run_worker
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import uuid

from redis import Redis

from ogi.agent.orchestrator import AgentOrchestrator, poll_orchestrator
from ogi.config import settings
from ogi.db.database import async_session_maker, close_db, init_db
from ogi.engine.transform_engine import TransformEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ogi.agent.worker")


def _build_worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4()}"


async def _run() -> None:
    await init_db()
    if async_session_maker is None:
        raise RuntimeError("Database session factory not initialized")

    transform_engine = TransformEngine()
    transform_engine.auto_discover()
    transform_engine.load_plugins(settings.plugin_dirs)
    logger.info("AI Investigator worker loaded %d transforms", len(transform_engine.list_transforms()))

    redis_conn: Redis | None = None  # type: ignore[type-arg]
    try:
        redis_conn = Redis.from_url(settings.redis_url)
        redis_conn.ping()
    except Exception:
        logger.warning("Redis not available for AI Investigator worker events")
        redis_conn = None

    worker_id = _build_worker_id()
    logger.info("Starting AI Investigator worker %s", worker_id)

    try:
        await poll_orchestrator(
            orchestrator_factory=lambda: AgentOrchestrator(
                session_factory=async_session_maker,
                worker_id=worker_id,
                redis_conn=redis_conn,
            )
        )
    finally:
        if redis_conn is not None:
            redis_conn.close()
        await close_db()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
