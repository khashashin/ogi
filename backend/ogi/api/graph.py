from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ogi.models import Entity, Edge
from ogi.api.dependencies import get_graph_engine, get_entity_store, get_edge_store
from ogi.engine import analysis

router = APIRouter(prefix="/projects/{project_id}/graph", tags=["graph"])


class GraphData:
    pass


@router.get("")
async def get_graph(project_id: UUID) -> dict[str, list[Entity] | list[Edge]]:
    """Get full graph data for a project (loads from DB into engine if needed)."""
    engine = get_graph_engine(project_id)

    # Hydrate from DB on first access
    if not engine._hydrated:
        entity_store = get_entity_store()
        edge_store = get_edge_store()
        entities = await entity_store.list_by_project(project_id)
        edges = await edge_store.list_by_project(project_id)
        for entity in entities:
            if not engine.get_entity(entity.id):
                engine.add_entity(entity)
        for edge in edges:
            try:
                engine.add_edge(edge)
            except ValueError:
                pass
        engine._hydrated = True

    return {
        "entities": list(engine.entities.values()),
        "edges": list(engine.edges.values()),
    }


@router.get("/neighbors/{entity_id}")
async def get_neighbors(project_id: UUID, entity_id: UUID) -> dict[str, list[Entity] | list[Edge]]:
    engine = get_graph_engine(project_id)
    neighbors = engine.get_neighbors(entity_id)
    edges = engine.get_edges_for_entity(entity_id)
    return {"entities": neighbors, "edges": edges}


@router.get("/stats")
async def get_stats(project_id: UUID) -> dict[str, int | float]:
    engine = get_graph_engine(project_id)
    return analysis.graph_stats(engine)


class AnalyzeRequest(BaseModel):
    algorithm: str


@router.post("/analyze")
async def analyze_graph(project_id: UUID, request: AnalyzeRequest) -> dict[str, object]:
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
