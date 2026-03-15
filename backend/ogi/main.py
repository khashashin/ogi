import logging
import traceback
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
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
)
from ogi.api.router import api_router

# Configure logging so all errors are visible in the terminal
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("ogi")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
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

    yield

    # Shutdown
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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all: log the full traceback so 500s are never silent."""
    logger.error("Unhandled exception on %s %s", request.method, request.url)
    logger.error(traceback.format_exc())
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
