from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from ogi.models import Edge, EdgeCreate, EdgeUpdate, UserProfile
from ogi.api.dependencies import get_edge_store, get_graph_engine
from ogi.api.auth import get_current_user

router = APIRouter(prefix="/projects/{project_id}/edges", tags=["edges"])


@router.post("", response_model=Edge, status_code=201)
async def create_edge(
    project_id: UUID,
    data: EdgeCreate,
    current_user: UserProfile = Depends(get_current_user),
) -> Edge:
    store = get_edge_store()
    edge = await store.create(project_id, data)
    engine = get_graph_engine(project_id)
    try:
        engine.add_edge(edge)
    except ValueError:
        pass  # entities may not be loaded in engine yet
    return edge


@router.get("", response_model=list[Edge])
async def list_edges(
    project_id: UUID,
    current_user: UserProfile = Depends(get_current_user),
) -> list[Edge]:
    store = get_edge_store()
    return await store.list_by_project(project_id)


@router.patch("/{edge_id}", response_model=Edge)
async def update_edge(
    project_id: UUID,
    edge_id: UUID,
    data: EdgeUpdate,
    current_user: UserProfile = Depends(get_current_user),
) -> Edge:
    store = get_edge_store()
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
    current_user: UserProfile = Depends(get_current_user),
) -> None:
    store = get_edge_store()
    deleted = await store.delete(edge_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Edge not found")
    engine = get_graph_engine(project_id)
    engine.remove_edge(edge_id)
