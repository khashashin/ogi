"""Project member management endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from ogi.models import UserProfile, ProjectMember, ProjectMemberCreate, ProjectMemberUpdate
from ogi.api.auth import get_current_user
from ogi.api.dependencies import get_project_store
from ogi.config import settings

router = APIRouter(prefix="/projects/{project_id}/members", tags=["members"])


# ---- helpers ----

async def _pool():  # type: ignore[no-untyped-def]
    """Return the asyncpg pool (members only work with PostgreSQL)."""
    from ogi.db.database import get_pg_pool
    return get_pg_pool()


# ---- endpoints ----

@router.get("", response_model=list[ProjectMember])
async def list_members(
    project_id: UUID,
    current_user: UserProfile = Depends(get_current_user),
) -> list[ProjectMember]:
    if settings.use_sqlite:
        return []  # members not supported in SQLite mode
    pool = await _pool()
    rows = await pool.fetch(
        """SELECT pm.project_id, pm.user_id, pm.role,
                  COALESCE(p.display_name, '') AS display_name,
                  COALESCE(p.email, '') AS email
           FROM project_members pm
           LEFT JOIN profiles p ON p.id = pm.user_id
           WHERE pm.project_id = $1""",
        project_id,
    )
    return [
        ProjectMember(
            project_id=r["project_id"],
            user_id=r["user_id"],
            role=r["role"],
            display_name=r["display_name"],
            email=r["email"],
        )
        for r in rows
    ]


@router.post("", response_model=ProjectMember, status_code=201)
async def add_member(
    project_id: UUID,
    data: ProjectMemberCreate,
    current_user: UserProfile = Depends(get_current_user),
) -> ProjectMember:
    if settings.use_sqlite:
        raise HTTPException(status_code=501, detail="Members not supported in SQLite mode")

    pool = await _pool()

    # Look up user by email
    profile = await pool.fetchrow("SELECT id, display_name, email FROM profiles WHERE email = $1", data.email)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")

    user_id: UUID = profile["id"]

    try:
        await pool.execute(
            "INSERT INTO project_members (project_id, user_id, role) VALUES ($1, $2, $3)",
            project_id, user_id, data.role,
        )
    except Exception:
        raise HTTPException(status_code=409, detail="User is already a member")

    return ProjectMember(
        project_id=project_id,
        user_id=user_id,
        role=data.role,
        display_name=profile["display_name"] or "",
        email=profile["email"] or "",
    )


@router.patch("/{user_id}", response_model=ProjectMember)
async def update_member(
    project_id: UUID,
    user_id: UUID,
    data: ProjectMemberUpdate,
    current_user: UserProfile = Depends(get_current_user),
) -> ProjectMember:
    if settings.use_sqlite:
        raise HTTPException(status_code=501, detail="Members not supported in SQLite mode")

    pool = await _pool()
    result = await pool.execute(
        "UPDATE project_members SET role = $1 WHERE project_id = $2 AND user_id = $3",
        data.role, project_id, user_id,
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Member not found")

    profile = await pool.fetchrow("SELECT display_name, email FROM profiles WHERE id = $1", user_id)
    return ProjectMember(
        project_id=project_id,
        user_id=user_id,
        role=data.role,
        display_name=(profile["display_name"] if profile else "") or "",
        email=(profile["email"] if profile else "") or "",
    )


@router.delete("/{user_id}", status_code=204)
async def remove_member(
    project_id: UUID,
    user_id: UUID,
    current_user: UserProfile = Depends(get_current_user),
) -> None:
    if settings.use_sqlite:
        raise HTTPException(status_code=501, detail="Members not supported in SQLite mode")

    pool = await _pool()
    result = await pool.execute(
        "DELETE FROM project_members WHERE project_id = $1 AND user_id = $2",
        project_id, user_id,
    )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Member not found")
