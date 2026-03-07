import asyncio
import logging
import traceback
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from pathlib import Path

from ogi.config import settings
from ogi.db.database import init_db, close_db
from ogi.engine.entity_registry import EntityRegistry
from ogi.engine.transform_engine import TransformEngine
from ogi.cli.registry import RegistryClient
from ogi.cli.installer import TransformInstaller
from ogi.api.dependencies import (
    init_transform_engine,
    init_entity_registry,
    init_plugin_engine,
    init_registry_client,
    init_transform_installer,
    init_redis,
)
from ogi.api.router import api_router

# Configure logging so all errors are visible in the terminal
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("ogi")


async def _run_startup_migrations() -> None:
    """Run Alembic migrations for non-SQLite app startups when enabled."""
    if settings.use_sqlite or not settings.auto_run_migrations:
        return

    from ogi.db.alembic_runner import adopt_and_upgrade

    await adopt_and_upgrade()


async def _recover_stale_jobs() -> None:
    """Mark any RUNNING/PENDING transform runs as FAILED on startup.

    If the server crashed while jobs were in progress, those runs will never
    complete.  This prevents them from appearing stuck in the UI forever.
    """
    from ogi.db.database import get_session
    from ogi.models import TransformStatus
    from sqlmodel import select, or_
    from datetime import datetime, timezone

    try:
        async for session in get_session():
            from ogi.models.transform import TransformRun
            stmt = select(TransformRun).where(
                or_(
                    TransformRun.status == TransformStatus.RUNNING,
                    TransformRun.status == TransformStatus.PENDING,
                )
            )
            result = await session.execute(stmt)
            stale_runs = list(result.scalars().all())
            for run in stale_runs:
                run.status = TransformStatus.FAILED
                run.error = "Server restarted while job was in progress"
                run.completed_at = datetime.now(timezone.utc)
                session.add(run)
            if stale_runs:
                await session.commit()
                logger.info("Recovered %d stale transform runs", len(stale_runs))
            break
    except Exception:
        logger.exception("Failed to recover stale jobs")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await _run_startup_migrations()

    # Startup DB connection
    await init_db()

    registry = EntityRegistry.instance()
    init_entity_registry(registry)

    transform_engine = TransformEngine()
    transform_engine.auto_discover()
    plugin_engine = transform_engine.load_plugins(settings.plugin_dirs)
    init_transform_engine(transform_engine)
    init_plugin_engine(plugin_engine)

    # Initialize registry client and installer
    from datetime import timedelta
    registry_client = RegistryClient(
        repo=settings.registry_repo,
        cache_ttl=timedelta(seconds=settings.registry_cache_ttl),
    )
    init_registry_client(registry_client)

    plugins_dir = Path(settings.plugin_dirs[0]).resolve()
    installer = TransformInstaller(
        registry=registry_client,
        plugins_dir=plugins_dir,
        ogi_version=app.version,
    )
    init_transform_installer(installer)

    # Initialize Redis + RQ queue
    pubsub_task: asyncio.Task | None = None  # type: ignore[type-arg]
    try:
        from redis import Redis
        from rq import Queue

        redis_conn = Redis.from_url(settings.redis_url)
        redis_conn.ping()  # verify connectivity
        queue = Queue(settings.rq_queue_name, connection=redis_conn)
        init_redis(redis_conn, queue)
        logger.info("Redis connected at %s", settings.redis_url)

        # Recover stale jobs from previous crash
        await _recover_stale_jobs()

        # Start Redis pub/sub → WebSocket bridge
        from ogi.api.websocket import redis_pubsub_listener
        pubsub_task = asyncio.create_task(redis_pubsub_listener())

    except Exception:
        logger.warning("Redis not available — transforms will fail to enqueue. Start Redis to enable the job queue.")

    yield

    # Shutdown
    if pubsub_task is not None:
        pubsub_task.cancel()
        try:
            await pubsub_task
        except asyncio.CancelledError:
            pass

    await close_db()


app = FastAPI(
    title="OGI — OpenGraph Intel",
    description="Open source link analysis and OSINT framework",
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


def _error_response(status_code: int, code: str, message: str, details: object | None = None) -> JSONResponse:
    payload: dict[str, object] = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if details is not None:
        payload["error"]["details"] = details  # type: ignore[index]
    return JSONResponse(status_code=status_code, content=payload)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if exc.status_code == 500 and not settings.expose_error_details:
        message = "Internal Server Error. Please try again later."
        details = None
    elif isinstance(detail, str):
        message = detail
        details: object | None = None
    else:
        message = "Request failed"
        details = detail
    return _error_response(
        status_code=exc.status_code,
        code=f"HTTP_{exc.status_code}",
        message=message,
        details=details,
    )


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return _error_response(
        status_code=422,
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details=exc.errors(),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all: log the full traceback so 500s are never silent."""
    logger.error("Unhandled exception on %s %s", request.method, request.url)
    logger.error(traceback.format_exc())
    details: dict[str, str] | None = None
    if settings.expose_error_details:
        details = {
            "type": exc.__class__.__name__,
            "message": str(exc),
        }
    return _error_response(
        status_code=500,
        code="INTERNAL_SERVER_ERROR",
        message="Internal Server Error. Please try again later. If the issue persists, contact support.",
        details=details,
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
