from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ogi.models import Entity, EntityCreate, EntityUpdate
from ogi.api.dependencies import get_entity_store, get_graph_engine
from ogi.api.auth import require_project_editor, require_project_viewer
from ogi.store.entity_store import EntityStore

router = APIRouter(prefix="/projects/{project_id}/entities", tags=["entities"])


class BulkDeleteEntitiesRequest(BaseModel):
    entity_ids: list[UUID]


class BulkDeleteEntitiesResponse(BaseModel):
    deleted_entity_ids: list[UUID]
    deleted_count: int


@router.post("", response_model=Entity, status_code=201)
async def create_entity(
    project_id: UUID,
    data: EntityCreate,
    _role: str = Depends(require_project_editor),
    store: EntityStore = Depends(get_entity_store),
) -> Entity:
    entity = await store.create(project_id, data)
    engine = get_graph_engine(project_id)
    engine.add_entity(entity)
    return entity


@router.get("", response_model=list[Entity])
async def list_entities(
    project_id: UUID,
    _role: str = Depends(require_project_viewer),
    store: EntityStore = Depends(get_entity_store),
) -> list[Entity]:
    return await store.list_by_project(project_id)


@router.get("/{entity_id}", response_model=Entity)
async def get_entity(
    project_id: UUID,
    entity_id: UUID,
    _role: str = Depends(require_project_viewer),
    store: EntityStore = Depends(get_entity_store),
) -> Entity:
    entity = await store.get(entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.patch("/{entity_id}", response_model=Entity)
async def update_entity(
    project_id: UUID,
    entity_id: UUID,
    data: EntityUpdate,
    _role: str = Depends(require_project_editor),
    store: EntityStore = Depends(get_entity_store),
) -> Entity:
    entity = await store.update(entity_id, data)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    engine = get_graph_engine(project_id)
    engine.add_entity(entity)  # update in-memory
    return entity


@router.delete("/{entity_id}", status_code=204)
async def delete_entity(
    project_id: UUID,
    entity_id: UUID,
    _role: str = Depends(require_project_editor),
    store: EntityStore = Depends(get_entity_store),
) -> None:
    deleted = await store.delete(entity_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Entity not found")
    engine = get_graph_engine(project_id)
    engine.remove_entity(entity_id)


@router.post("/bulk-delete", response_model=BulkDeleteEntitiesResponse)
async def bulk_delete_entities(
    project_id: UUID,
    data: BulkDeleteEntitiesRequest,
    _role: str = Depends(require_project_editor),
    store: EntityStore = Depends(get_entity_store),
) -> BulkDeleteEntitiesResponse:
    deleted_ids = await store.delete_many(project_id, data.entity_ids)
    engine = get_graph_engine(project_id)
    for entity_id in deleted_ids:
        engine.remove_entity(entity_id)
    return BulkDeleteEntitiesResponse(
        deleted_entity_ids=deleted_ids,
        deleted_count=len(deleted_ids),
    )
