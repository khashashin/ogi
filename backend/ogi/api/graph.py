from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ogi.models import Entity, Edge
from ogi.api.dependencies import get_graph_engine, get_entity_store, get_edge_store
from ogi.api.auth import require_project_viewer
from ogi.store.entity_store import EntityStore
from ogi.store.edge_store import EdgeStore
from ogi.engine import analysis

router = APIRouter(prefix="/projects/{project_id}/graph", tags=["graph"])


class GraphData:
    pass


def _normalize_dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


@router.get("")
async def get_graph(
    project_id: UUID,
    refresh: bool = False,
    _role: str = Depends(require_project_viewer),
    entity_store: EntityStore = Depends(get_entity_store),
    edge_store: EdgeStore = Depends(get_edge_store),
) -> dict[str, list[Entity] | list[Edge]]:
    """Get full graph data for a project.

    Hydrates in-memory state from DB once per project process. Use
    `refresh=true` to force a DB re-sync for out-of-band writes.
    """
    engine = get_graph_engine(project_id)

    if refresh or not engine.is_hydrated:
        if refresh:
            engine.clear()

        entities = await entity_store.list_by_project(project_id)
        edges = await edge_store.list_by_project(project_id)
        for entity in entities:
            if not engine.get_entity(entity.id):
                engine.add_entity(entity)
        for edge in edges:
            if edge.id in engine.edges:
                continue
            try:
                engine.add_edge(edge)
            except ValueError:
                pass
        engine.mark_hydrated()

    return {
        "entities": list(engine.entities.values()),
        "edges": list(engine.edges.values()),
    }


@router.get("/window")
async def get_graph_window(
    project_id: UUID,
    from_ts: datetime | None = Query(None, alias="from"),
    to_ts: datetime | None = Query(None, alias="to"),
    _role: str = Depends(require_project_viewer),
    entity_store: EntityStore = Depends(get_entity_store),
    edge_store: EdgeStore = Depends(get_edge_store),
) -> dict[str, list[Entity] | list[Edge]]:
    """Return graph slice constrained to a time window."""
    from_ts = _normalize_dt(from_ts)
    to_ts = _normalize_dt(to_ts)

    entities = await entity_store.list_by_project(project_id)
    edges = await edge_store.list_by_project(project_id)

    window_edges = [
        edge for edge in edges
        if (from_ts is None or _normalize_dt(edge.created_at) >= from_ts)
        and (to_ts is None or _normalize_dt(edge.created_at) <= to_ts)
    ]

    window_entity_ids = {
        entity.id for entity in entities
        if (from_ts is None or _normalize_dt(entity.created_at) >= from_ts)
        and (to_ts is None or _normalize_dt(entity.created_at) <= to_ts)
    }
    for edge in window_edges:
        window_entity_ids.add(edge.source_id)
        window_entity_ids.add(edge.target_id)

    window_entities = [entity for entity in entities if entity.id in window_entity_ids]
    valid_ids = {entity.id for entity in window_entities}
    window_edges = [
        edge for edge in window_edges
        if edge.source_id in valid_ids and edge.target_id in valid_ids
    ]

    return {"entities": window_entities, "edges": window_edges}


@router.get("/neighbors/{entity_id}")
async def get_neighbors(
    project_id: UUID,
    entity_id: UUID,
    _role: str = Depends(require_project_viewer),
) -> dict[str, list[Entity] | list[Edge]]:
    engine = get_graph_engine(project_id)
    neighbors = engine.get_neighbors(entity_id)
    edges = engine.get_edges_for_entity(entity_id)
    return {"entities": neighbors, "edges": edges}


@router.get("/stats")
async def get_stats(
    project_id: UUID,
    _role: str = Depends(require_project_viewer),
) -> dict[str, int | float]:
    engine = get_graph_engine(project_id)
    return analysis.graph_stats(engine)


class AnalyzeRequest(BaseModel):
    algorithm: str


@router.post("/analyze")
async def analyze_graph(
    project_id: UUID,
    request: AnalyzeRequest,
    _role: str = Depends(require_project_viewer),
) -> dict[str, object]:
    engine = get_graph_engine(project_id)

    algorithms: dict[str, object] = {
        "degree_centrality": lambda: {"scores": {str(k): v for k, v in analysis.degree_centrality(engine).items()}},
        "betweenness_centrality": lambda: {"scores": {str(k): v for k, v in analysis.betweenness_centrality(engine).items()}},
        "closeness_centrality": lambda: {"scores": {str(k): v for k, v in analysis.closeness_centrality(engine).items()}},
        "pagerank": lambda: {"scores": {str(k): v for k, v in analysis.pagerank(engine).items()}},
        "connected_components": lambda: {"communities": [[str(eid) for eid in c] for c in analysis.connected_components(engine)]},
    }

    algo_fn = algorithms.get(request.algorithm)
    if algo_fn is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown algorithm '{request.algorithm}'. Available: {list(algorithms.keys())}",
        )

    return algo_fn()  # type: ignore[return-value]
