from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from ogi.models import Entity, EntityCreate, EntityUpdate, UserProfile
from ogi.api.dependencies import get_entity_store, get_graph_engine
from ogi.api.auth import get_current_user, require_project_editor, require_project_viewer
from ogi.store.entity_store import EntityStore

router = APIRouter(prefix="/projects/{project_id}/entities", tags=["entities"])


@router.post("", response_model=Entity, status_code=201)
async def create_entity(
    project_id: UUID,
    data: EntityCreate,
    role: str = Depends(require_project_editor),
    current_user: UserProfile = Depends(get_current_user),
    store: EntityStore = Depends(get_entity_store),
) -> Entity:
    entity = await store.create(project_id, data)
    engine = get_graph_engine(project_id)
    engine.add_entity(entity)
    return entity


@router.get("", response_model=list[Entity])
async def list_entities(
    project_id: UUID,
    role: str = Depends(require_project_viewer),
    current_user: UserProfile = Depends(get_current_user),
    store: EntityStore = Depends(get_entity_store),
) -> list[Entity]:
    return await store.list_by_project(project_id)


@router.get("/{entity_id}", response_model=Entity)
async def get_entity(
    project_id: UUID,
    entity_id: UUID,
    role: str = Depends(require_project_viewer),
    current_user: UserProfile = Depends(get_current_user),
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
    role: str = Depends(require_project_editor),
    current_user: UserProfile = Depends(get_current_user),
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
    role: str = Depends(require_project_editor),
    current_user: UserProfile = Depends(get_current_user),
    store: EntityStore = Depends(get_entity_store),
) -> None:
    deleted = await store.delete(entity_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Entity not found")
    engine = get_graph_engine(project_id)
    engine.remove_entity(entity_id)
