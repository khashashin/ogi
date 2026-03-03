from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from ogi.models import Edge, EdgeCreate, EdgeUpdate
from ogi.api.dependencies import get_edge_store, get_graph_engine
from ogi.api.auth import require_project_editor, require_project_viewer
from ogi.store.edge_store import EdgeStore

router = APIRouter(prefix="/projects/{project_id}/edges", tags=["edges"])


@router.post("", response_model=Edge, status_code=201)
async def create_edge(
    project_id: UUID,
    data: EdgeCreate,
    _role: str = Depends(require_project_editor),
    store: EdgeStore = Depends(get_edge_store),
) -> Edge:
    try:
        edge = await store.create(project_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    engine = get_graph_engine(project_id)
    try:
        engine.add_edge(edge)
    except ValueError:
        pass  # entities may not be loaded in engine yet
    return edge


@router.get("", response_model=list[Edge])
async def list_edges(
    project_id: UUID,
    _role: str = Depends(require_project_viewer),
    store: EdgeStore = Depends(get_edge_store),
) -> list[Edge]:
    return await store.list_by_project(project_id)


@router.patch("/{edge_id}", response_model=Edge)
async def update_edge(
    project_id: UUID,
    edge_id: UUID,
    data: EdgeUpdate,
    _role: str = Depends(require_project_editor),
    store: EdgeStore = Depends(get_edge_store),
) -> Edge:
    edge = await store.update(edge_id, data)
    if edge is None:
        raise HTTPException(status_code=404, detail="Edge not found")
    engine = get_graph_engine(project_id)
    # Update in-memory: remove old, add new
    engine.remove_edge(edge_id)
    try:
        engine.add_edge(edge)
    except ValueError:
        pass
    return edge


@router.delete("/{edge_id}", status_code=204)
async def delete_edge(
    project_id: UUID,
    edge_id: UUID,
    _role: str = Depends(require_project_editor),
    store: EdgeStore = Depends(get_edge_store),
) -> None:
    deleted = await store.delete(edge_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Edge not found")
    engine = get_graph_engine(project_id)
    engine.remove_edge(edge_id)
