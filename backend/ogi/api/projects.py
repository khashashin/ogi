from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from ogi.models import Project, ProjectCreate, ProjectUpdate, UserProfile
from ogi.api.auth import get_current_user, require_project_viewer, require_project_editor, require_project_owner
from ogi.api.dependencies import get_project_store
from ogi.store.project_store import ProjectStore

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=Project, status_code=201)
async def create_project(
    data: ProjectCreate,
    current_user: UserProfile = Depends(get_current_user),
    store: ProjectStore = Depends(get_project_store),
) -> Project:
    return await store.create(data, current_user.id)


@router.get("", response_model=list[Project])
async def list_projects(
    current_user: UserProfile = Depends(get_current_user),
    store: ProjectStore = Depends(get_project_store),
) -> list[Project]:
    return await store.list_all(current_user.id)


@router.get("/{project_id}", response_model=Project)
async def get_project(
    project_id: UUID,
    role: str = Depends(require_project_viewer),
    current_user: UserProfile = Depends(get_current_user),
    store: ProjectStore = Depends(get_project_store),
) -> Project:
    project = await store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return project


@router.patch("/{project_id}", response_model=Project)
async def update_project(
    project_id: UUID,
    data: ProjectUpdate,
    role: str = Depends(require_project_editor),
    current_user: UserProfile = Depends(get_current_user),
    store: ProjectStore = Depends(get_project_store),
) -> Project:
    project = await store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    updated = await store.update(project_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Project not found")
    return updated


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: UUID,
    role: str = Depends(require_project_owner),
    current_user: UserProfile = Depends(get_current_user),
    store: ProjectStore = Depends(get_project_store),
) -> None:
    project = await store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    deleted = await store.delete(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
