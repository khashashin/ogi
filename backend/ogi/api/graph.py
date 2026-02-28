from uuid import UUID

from fastapi import APIRouter

from ogi.models import Entity, Edge
from ogi.api.dependencies import get_graph_engine, get_entity_store, get_edge_store

router = APIRouter(prefix="/projects/{project_id}/graph", tags=["graph"])


class GraphData:
    pass


@router.get("")
async def get_graph(project_id: UUID) -> dict[str, list[Entity] | list[Edge]]:
    """Get full graph data for a project (loads from DB into engine if needed)."""
    engine = get_graph_engine(project_id)

    # If engine is empty, load from DB
    if not engine.entities:
        entity_store = get_entity_store()
        edge_store = get_edge_store()
        entities = await entity_store.list_by_project(project_id)
        edges = await edge_store.list_by_project(project_id)
        for entity in entities:
            engine.add_entity(entity)
        for edge in edges:
            try:
                engine.add_edge(edge)
            except ValueError:
                pass

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
