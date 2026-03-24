from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from ogi.models import Entity, EntityCreate, EntityUpdate
from ogi.api.dependencies import get_entity_store, get_graph_engine
from ogi.api.auth import require_project_editor, require_project_viewer
from ogi.store.entity_store import EntityStore
from ogi.models.entity import EntityType
from ogi.config import settings
from ogi.media_storage import (
    load_local_media,
    load_supabase_media,
    store_person_visual_image,
)

router = APIRouter(prefix="/projects/{project_id}/entities", tags=["entities"])


class BulkDeleteEntitiesRequest(BaseModel):
    entity_ids: list[UUID]


class BulkDeleteEntitiesResponse(BaseModel):
    deleted_entity_ids: list[UUID]
    deleted_count: int


class PersonImageUploadResponse(BaseModel):
    image_url: str
    storage_backend: str
    entity: Entity


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


@router.post("/{entity_id}/person-image", response_model=PersonImageUploadResponse)
async def upload_person_image(
    project_id: UUID,
    entity_id: UUID,
    file: UploadFile = File(...),
    _role: str = Depends(require_project_editor),
    store: EntityStore = Depends(get_entity_store),
) -> PersonImageUploadResponse:
    entity = await store.get(entity_id)
    if entity is None or entity.project_id != project_id:
        raise HTTPException(status_code=404, detail="Entity not found")
    if entity.type != EntityType.PERSON:
        raise HTTPException(status_code=400, detail="Only Person entities can use uploaded images")

    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(content) > settings.media_upload_max_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image is too large")

    stored = store_person_visual_image(
        project_id=project_id,
        entity_id=entity_id,
        filename=file.filename,
        content_type=content_type,
        content=content,
    )

    updated = await store.update(
        entity_id,
        EntityUpdate(
            properties={
                **entity.properties,
                "visual_image_backend": stored.backend,
                "visual_image_path": stored.path,
                "visual_image_content_type": stored.content_type,
                "visual_image_url": f"/api/v1/projects/{project_id}/entities/{entity_id}/person-image",
            }
        ),
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    engine = get_graph_engine(project_id)
    engine.add_entity(updated)
    return PersonImageUploadResponse(
        image_url=f"/api/v1/projects/{project_id}/entities/{entity_id}/person-image",
        storage_backend=stored.backend,
        entity=updated,
    )


@router.get("/{entity_id}/person-image")
async def get_person_image(
    project_id: UUID,
    entity_id: UUID,
    _role: str = Depends(require_project_viewer),
    store: EntityStore = Depends(get_entity_store),
) -> Response:
    entity = await store.get(entity_id)
    if entity is None or entity.project_id != project_id:
        raise HTTPException(status_code=404, detail="Entity not found")
    if entity.type != EntityType.PERSON:
        raise HTTPException(status_code=400, detail="Only Person entities can use uploaded images")

    properties = entity.properties or {}
    backend = properties.get("visual_image_backend")
    path = properties.get("visual_image_path")
    content_type = properties.get("visual_image_content_type")

    if isinstance(backend, str) and isinstance(path, str) and path.strip():
        try:
            if backend == "local":
                payload = load_local_media(path, content_type=content_type if isinstance(content_type, str) else None)
            elif backend == "supabase":
                payload = await load_supabase_media(path, content_type=content_type if isinstance(content_type, str) else None)
            else:
                raise HTTPException(status_code=404, detail="Image not found")
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Image not found")
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Image fetch failed: {exc}") from exc

        return Response(content=payload.content, media_type=payload.content_type)

    legacy_url = properties.get("visual_image_url")
    if isinstance(legacy_url, str) and legacy_url.strip():
        raise HTTPException(
            status_code=410,
            detail="Legacy public image URLs are no longer served through this endpoint",
        )

    raise HTTPException(status_code=404, detail="Image not found")


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
