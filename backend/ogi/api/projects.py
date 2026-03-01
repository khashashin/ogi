from uuid import UUID

from fastapi import APIRouter, HTTPException

from ogi.models import Project, ProjectCreate, ProjectUpdate
from ogi.api.dependencies import get_project_store

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=Project, status_code=201)
async def create_project(data: ProjectCreate) -> Project:
    store = get_project_store()
    return await store.create(data)


@router.get("", response_model=list[Project])
async def list_projects() -> list[Project]:
    store = get_project_store()
    return await store.list_all()


@router.get("/{project_id}", response_model=Project)
async def get_project(project_id: UUID) -> Project:
    store = get_project_store()
    project = await store.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=Project)
async def update_project(project_id: UUID, data: ProjectUpdate) -> Project:
    store = get_project_store()
    project = await store.update(project_id, data)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: UUID) -> None:
    store = get_project_store()
    deleted = await store.delete(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
