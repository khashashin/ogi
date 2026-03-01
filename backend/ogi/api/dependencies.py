"""Shared singletons for API route handlers."""
from uuid import UUID

from ogi.engine.entity_registry import EntityRegistry
from ogi.engine.graph_engine import GraphEngine
from ogi.engine.transform_engine import TransformEngine
from ogi.store.project_store import ProjectStore
from ogi.store.entity_store import EntityStore
from ogi.store.edge_store import EdgeStore
from ogi.store.transform_run_store import TransformRunStore

_project_store: ProjectStore | None = None
_entity_store: EntityStore | None = None
_edge_store: EdgeStore | None = None
_transform_run_store: TransformRunStore | None = None
_transform_engine: TransformEngine | None = None
_entity_registry: EntityRegistry | None = None
_graph_engines: dict[UUID, GraphEngine] = {}


def init_stores(
    project_store: ProjectStore,
    entity_store: EntityStore,
    edge_store: EdgeStore,
    transform_run_store: TransformRunStore | None = None,
) -> None:
    global _project_store, _entity_store, _edge_store, _transform_run_store
    _project_store = project_store
    _entity_store = entity_store
    _edge_store = edge_store
    _transform_run_store = transform_run_store


def init_transform_engine(engine: TransformEngine) -> None:
    global _transform_engine
    _transform_engine = engine


def init_entity_registry(registry: EntityRegistry) -> None:
    global _entity_registry
    _entity_registry = registry


def get_project_store() -> ProjectStore:
    assert _project_store is not None
    return _project_store


def get_entity_store() -> EntityStore:
    assert _entity_store is not None
    return _entity_store


def get_edge_store() -> EdgeStore:
    assert _edge_store is not None
    return _edge_store


def get_transform_engine() -> TransformEngine:
    assert _transform_engine is not None
    return _transform_engine


def get_entity_registry() -> EntityRegistry:
    assert _entity_registry is not None
    return _entity_registry


def get_transform_run_store() -> TransformRunStore:
    assert _transform_run_store is not None
    return _transform_run_store


def get_graph_engine(project_id: UUID) -> GraphEngine:
    if project_id not in _graph_engines:
        _graph_engines[project_id] = GraphEngine()
    return _graph_engines[project_id]
