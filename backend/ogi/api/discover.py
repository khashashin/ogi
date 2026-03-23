"""Public project discovery endpoint — no auth required."""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from ogi.models import ProjectDiscoverRead
from ogi.api.auth import get_current_user
from ogi.api.dependencies import get_project_store
from ogi.store.project_store import ProjectStore

router = APIRouter(prefix="/discover", tags=["discover"])
logger = logging.getLogger(__name__)


@router.get("", response_model=list[ProjectDiscoverRead])
async def discover_projects(
    q: str | None = None,
    request: Request = None,
    store: ProjectStore = Depends(get_project_store),
) -> list[ProjectDiscoverRead]:
    """List all public projects. Optionally filter by name/description with ?q=."""
    projects_with_owners = await store.list_public(search=q)

    # Try to get current user for bookmark status (optional, no auth required)
    bookmarked_ids: set[UUID] = set()
    try:
        from ogi.db.database import get_session
        async for session in get_session():
            auth_header = request.headers.get("Authorization", "") if request else ""
            if auth_header.startswith("Bearer "):
                user = await get_current_user(request, session)
                if user and user.id != UUID("00000000-0000-0000-0000-000000000000"):
                    bookmarked_ids = await store.get_bookmarked_ids(user.id)
    except Exception:
        logger.exception("Failed to resolve discover bookmark status")

    return [
        ProjectDiscoverRead(
            id=project.id,
            name=project.name,
            description=project.description,
            owner_id=project.owner_id,
            owner_name=owner_name,
            is_public=project.is_public,
            created_at=project.created_at,
            updated_at=project.updated_at,
            is_bookmarked=project.id in bookmarked_ids,
        )
        for project, owner_name in projects_with_owners
    ]
