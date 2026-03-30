from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from ogi.models import Project, ProjectCreate, ProjectUpdate, UserProfile, ProjectDiscoverRead, ProjectWithRole
from ogi.api.auth import get_current_user, require_project_viewer, require_project_editor, require_project_owner
from ogi.api.dependencies import get_project_store
from ogi.store.project_store import ProjectStore

router = APIRouter(prefix="/projects", tags=["projects"])


class MyProjectRead(ProjectDiscoverRead):
    source: str = "owned"  # "owned" | "member" | "bookmarked"
    role: str = "owner"


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


@router.get("/my", response_model=list[MyProjectRead])
async def list_my_projects(
    current_user: UserProfile = Depends(get_current_user),
    store: ProjectStore = Depends(get_project_store),
) -> list[MyProjectRead]:
    """Return user's projects: owned, member of, and bookmarked."""
    items = await store.list_my_projects(current_user.id)
    return [
        MyProjectRead(
            id=item["project"].id,
            name=item["project"].name,
            description=item["project"].description,
            owner_id=item["project"].owner_id,
            is_public=item["project"].is_public,
            created_at=item["project"].created_at,
            updated_at=item["project"].updated_at,
            source=item["source"],
            role=item["role"],
        )
        for item in items
    ]


@router.get("/{project_id}", response_model=ProjectWithRole)
async def get_project(
    project_id: UUID,
    role: str = Depends(require_project_viewer),
    store: ProjectStore = Depends(get_project_store),
) -> ProjectWithRole:
    project = await store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return ProjectWithRole(**project.model_dump(), role=role)


@router.patch("/{project_id}", response_model=Project)
async def update_project(
    project_id: UUID,
    data: ProjectUpdate,
    _role: str = Depends(require_project_editor),
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
    _role: str = Depends(require_project_owner),
    store: ProjectStore = Depends(get_project_store),
) -> None:
    project = await store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    deleted = await store.delete(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")


# --- Bookmarks ---

@router.post("/{project_id}/bookmark", status_code=201)
async def bookmark_project(
    project_id: UUID,
    current_user: UserProfile = Depends(get_current_user),
    store: ProjectStore = Depends(get_project_store),
) -> dict:
    """Bookmark a public project."""
    project = await store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.is_public:
        raise HTTPException(status_code=403, detail="Can only bookmark public projects")

    created = await store.add_bookmark(current_user.id, project_id)
    if not created:
        raise HTTPException(status_code=409, detail="Already bookmarked")
    return {"status": "bookmarked"}


@router.delete("/{project_id}/bookmark", status_code=204)
async def unbookmark_project(
    project_id: UUID,
    current_user: UserProfile = Depends(get_current_user),
    store: ProjectStore = Depends(get_project_store),
) -> None:
    """Remove a project bookmark."""
    removed = await store.remove_bookmark(current_user.id, project_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Bookmark not found")
