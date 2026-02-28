from uuid import UUID

from fastapi import APIRouter, HTTPException

from ogi.models import Entity, EntityCreate, EntityUpdate
from ogi.api.dependencies import get_entity_store, get_graph_engine

router = APIRouter(prefix="/projects/{project_id}/entities", tags=["entities"])


@router.post("", response_model=Entity, status_code=201)
async def create_entity(project_id: UUID, data: EntityCreate) -> Entity:
    store = get_entity_store()
    entity = await store.create(project_id, data)
    engine = get_graph_engine(project_id)
    engine.add_entity(entity)
    return entity


@router.get("", response_model=list[Entity])
async def list_entities(project_id: UUID) -> list[Entity]:
    store = get_entity_store()
    return await store.list_by_project(project_id)


@router.get("/{entity_id}", response_model=Entity)
async def get_entity(project_id: UUID, entity_id: UUID) -> Entity:
    store = get_entity_store()
    entity = await store.get(entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.patch("/{entity_id}", response_model=Entity)
async def update_entity(project_id: UUID, entity_id: UUID, data: EntityUpdate) -> Entity:
    store = get_entity_store()
    entity = await store.update(entity_id, data)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    engine = get_graph_engine(project_id)
    engine.add_entity(entity)  # update in-memory
    return entity


@router.delete("/{entity_id}", status_code=204)
async def delete_entity(project_id: UUID, entity_id: UUID) -> None:
    store = get_entity_store()
    deleted = await store.delete(entity_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Entity not found")
    engine = get_graph_engine(project_id)
    engine.remove_entity(entity_id)
