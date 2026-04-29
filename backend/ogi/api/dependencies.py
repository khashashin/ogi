"""Shared singletons for API route handlers."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated, TYPE_CHECKING
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ogi.db.database import get_session
from ogi.engine.entity_registry import EntityRegistry
from ogi.engine.graph_engine import GraphEngine
from ogi.engine.transform_engine import TransformEngine
from ogi.engine.plugin_engine import PluginEngine
from ogi.cli.registry import RegistryClient
from ogi.cli.installer import TransformInstaller
from ogi.store.project_store import ProjectStore
from ogi.store.entity_store import EntityStore
from ogi.store.edge_store import EdgeStore
from ogi.store.transform_run_store import TransformRunStore
from ogi.store.api_key_store import ApiKeyStore
from ogi.store.user_plugin_preference_store import UserPluginPreferenceStore
from ogi.store.transform_settings_store import TransformSettingsStore
from ogi.store.audit_log_store import AuditLogStore
from ogi.store.project_event_store import ProjectEventStore
from ogi.store.timeline_store import TimelineStore
from ogi.store.map_store import MapStore
from ogi.store.location_search_store import LocationSearchStore

if TYPE_CHECKING:
    from redis import Redis as SyncRedis
    from rq import Queue

_transform_engine: TransformEngine | None = None
_entity_registry: EntityRegistry | None = None
_plugin_engine: PluginEngine | None = None
_registry_client: RegistryClient | None = None
_transform_installer: TransformInstaller | None = None
_graph_engines: dict[UUID, GraphEngine] = {}
_redis_conn: SyncRedis | None = None  # type: ignore[type-arg]
_rq_queue: Queue | None = None

# We still need to fake the init_stores for main.py signature compatibility for now,
# but we just ignore the arguments since stores are now request-scoped
def init_stores(
    project_store: ProjectStore | None = None,
    entity_store: EntityStore | None = None,
    edge_store: EdgeStore | None = None,
    transform_run_store: TransformRunStore | None = None,
) -> None:
    pass


def init_transform_engine(engine: TransformEngine) -> None:
    global _transform_engine
    _transform_engine = engine


def init_entity_registry(registry: EntityRegistry) -> None:
    global _entity_registry
    _entity_registry = registry


def init_api_key_store(store: ApiKeyStore | None = None) -> None:
    pass


def init_plugin_engine(engine: PluginEngine) -> None:
    global _plugin_engine
    _plugin_engine = engine


async def get_project_store(session: AsyncSession = Depends(get_session)) -> ProjectStore:
    return ProjectStore(session)


async def get_entity_store(session: AsyncSession = Depends(get_session)) -> EntityStore:
    return EntityStore(session)


async def get_edge_store(session: AsyncSession = Depends(get_session)) -> EdgeStore:
    return EdgeStore(session)


def get_transform_engine() -> TransformEngine:
    assert _transform_engine is not None
    return _transform_engine


def get_entity_registry() -> EntityRegistry:
    assert _entity_registry is not None
    return _entity_registry


async def get_transform_run_store(session: AsyncSession = Depends(get_session)) -> TransformRunStore:
    return TransformRunStore(session)


async def get_api_key_store(session: AsyncSession = Depends(get_session)) -> ApiKeyStore:
    return ApiKeyStore(session)


async def get_user_plugin_preference_store(
    session: AsyncSession = Depends(get_session),
) -> UserPluginPreferenceStore:
    return UserPluginPreferenceStore(session)


async def get_transform_settings_store(
    session: AsyncSession = Depends(get_session),
) -> TransformSettingsStore:
    return TransformSettingsStore(session)


async def get_audit_log_store(
    session: AsyncSession = Depends(get_session),
) -> AuditLogStore:
    return AuditLogStore(session)


async def get_project_event_store(
    session: AsyncSession = Depends(get_session),
) -> ProjectEventStore:
    return ProjectEventStore(session)


async def get_timeline_store(
    session: AsyncSession = Depends(get_session),
) -> TimelineStore:
    return TimelineStore(session)


async def get_map_store(
    session: AsyncSession = Depends(get_session),
) -> MapStore:
    return MapStore(session)


async def get_location_search_store(
    session: AsyncSession = Depends(get_session),
) -> LocationSearchStore:
    return LocationSearchStore(session)


def get_plugin_engine() -> PluginEngine:
    assert _plugin_engine is not None
    return _plugin_engine


def init_registry_client(client: RegistryClient) -> None:
    global _registry_client
    _registry_client = client


def init_transform_installer(installer: TransformInstaller) -> None:
    global _transform_installer
    _transform_installer = installer


def get_registry_client() -> RegistryClient:
    assert _registry_client is not None
    return _registry_client


def get_transform_installer() -> TransformInstaller:
    assert _transform_installer is not None
    return _transform_installer


def get_graph_engine(project_id: UUID) -> GraphEngine:
    if project_id not in _graph_engines:
        _graph_engines[project_id] = GraphEngine()
    return _graph_engines[project_id]


# --- Redis / RQ ---

def init_redis(conn: SyncRedis, queue: Queue) -> None:  # type: ignore[type-arg]
    global _redis_conn, _rq_queue
    _redis_conn = conn
    _rq_queue = queue


def get_redis() -> SyncRedis | None:  # type: ignore[type-arg]
    return _redis_conn


def get_rq_queue() -> Queue | None:
    return _rq_queue
