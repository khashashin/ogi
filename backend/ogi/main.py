from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ogi.config import settings
from ogi.db.database import get_sqlite_db, close_db, create_pg_pool
from ogi.db.migrations import run_migrations
from ogi.engine.entity_registry import EntityRegistry
from ogi.engine.transform_engine import TransformEngine
from ogi.store.project_store import ProjectStore
from ogi.store.entity_store import EntityStore
from ogi.store.edge_store import EdgeStore
from ogi.store.transform_run_store import TransformRunStore
from ogi.store.api_key_store import ApiKeyStore
from ogi.api.dependencies import init_stores, init_transform_engine, init_entity_registry, init_plugin_engine, init_api_key_store
from ogi.api.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup — choose DB backend
    if settings.use_sqlite:
        db = await get_sqlite_db()
    else:
        db = await create_pg_pool()

    await run_migrations(db)

    init_stores(
        project_store=ProjectStore(db),
        entity_store=EntityStore(db),
        edge_store=EdgeStore(db),
        transform_run_store=TransformRunStore(db),
    )

    registry = EntityRegistry.instance()
    init_entity_registry(registry)

    transform_engine = TransformEngine()
    transform_engine.auto_discover()
    plugin_engine = transform_engine.load_plugins(settings.plugin_dirs)
    init_transform_engine(transform_engine)
    init_plugin_engine(plugin_engine)
    init_api_key_store(ApiKeyStore(db))

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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
