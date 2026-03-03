"""Project member management endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, delete
from supabase import create_client

from ogi.models import UserProfile, ProjectMember, ProjectMemberCreate, ProjectMemberUpdate
from ogi.models.auth import ProjectMemberRead
from ogi.api.auth import get_current_user, require_project_viewer, require_project_owner
from ogi.api.dependencies import get_project_store
from ogi.db.database import get_session
from ogi.config import settings


async def _find_or_create_profile_by_email(email: str, session: AsyncSession) -> UserProfile | None:
    """Look up a user profile by email, falling back to Supabase admin API if needed."""
    # First check local profiles table
    stmt = select(UserProfile).where(UserProfile.email == email)
    result = await session.execute(stmt)
    profile = result.scalar_one_or_none()
    if profile:
        return profile

    # Not found locally — try Supabase admin API to find the user
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return None

    try:
        admin_client = create_client(settings.supabase_url, settings.supabase_service_role_key)
        # List users filtered by email (admin endpoint)
        users_response = admin_client.auth.admin.list_users()
        matched_user = None
        for u in users_response:
            if u.email == email:
                matched_user = u
                break

        if not matched_user:
            return None

        # Create profile locally so FK constraints work
        user_id = UUID(str(matched_user.id))
        profile = UserProfile(
            id=user_id,
            email=email,
            display_name=matched_user.user_metadata.get("display_name", "") if matched_user.user_metadata else "",
        )
        session.add(profile)
        await session.commit()
        await session.refresh(profile)
        return profile
    except Exception:
        return None

router = APIRouter(prefix="/projects/{project_id}/members", tags=["members"])


@router.get("", response_model=list[ProjectMemberRead])
async def list_members(
    project_id: UUID,
    _role: str = Depends(require_project_viewer),
    session: AsyncSession = Depends(get_session),
) -> list[ProjectMemberRead]:
    if settings.use_sqlite:
        return []

    # Join ProjectMember with UserProfile (profiles table)
    stmt = (
        select(ProjectMember, UserProfile)
        .join(UserProfile, ProjectMember.user_id == UserProfile.id, isouter=True)
        .where(ProjectMember.project_id == project_id)
    )
    result = await session.execute(stmt)
    
    response = []
    for member, profile in result.all():
        response.append(
            ProjectMemberRead(
                project_id=member.project_id,
                user_id=member.user_id,
                role=member.role,
                display_name=profile.display_name if profile else "",
                email=profile.email if profile else "",
            )
        )
    return response


@router.post("", response_model=ProjectMemberRead, status_code=201)
async def add_member(
    project_id: UUID,
    data: ProjectMemberCreate,
    _role: str = Depends(require_project_owner),
    session: AsyncSession = Depends(get_session),
) -> ProjectMemberRead:
    if settings.use_sqlite:
        raise HTTPException(status_code=501, detail="Members not supported in SQLite mode")

    # Look up user by email (checks local DB, then Supabase auth)
    profile = await _find_or_create_profile_by_email(data.email, session)
    
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if already a member
    existing_stmt = select(ProjectMember).where(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == profile.id
    )
    existing_result = await session.execute(existing_stmt)
    if existing_result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="User is already a member")

    member = ProjectMember(project_id=project_id, user_id=profile.id, role=data.role)
    session.add(member)
    await session.commit()

    return ProjectMemberRead(
        project_id=project_id,
        user_id=profile.id,
        role=data.role,
        display_name=profile.display_name,
        email=profile.email,
    )


@router.patch("/{user_id}", response_model=ProjectMemberRead)
async def update_member(
    project_id: UUID,
    user_id: UUID,
    data: ProjectMemberUpdate,
    _role: str = Depends(require_project_owner),
    session: AsyncSession = Depends(get_session),
) -> ProjectMemberRead:
    if settings.use_sqlite:
        raise HTTPException(status_code=501, detail="Members not supported in SQLite mode")

    stmt = select(ProjectMember).where(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user_id
    )
    result = await session.execute(stmt)
    member = result.scalar_one_or_none()
    
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    member.role = data.role
    session.add(member)
    await session.commit()

    # Get profile for response
    profile_stmt = select(UserProfile).where(UserProfile.id == user_id)
    profile_result = await session.execute(profile_stmt)
    profile = profile_result.scalar_one_or_none()

    return ProjectMemberRead(
        project_id=project_id,
        user_id=user_id,
        role=data.role,
        display_name=profile.display_name if profile else "",
        email=profile.email if profile else "",
    )


@router.delete("/{user_id}", status_code=204)
async def remove_member(
    project_id: UUID,
    user_id: UUID,
    current_user: UserProfile = Depends(get_current_user),
    store: ProjectStore = Depends(get_project_store),
    session: AsyncSession = Depends(get_session),
) -> None:
    if settings.use_sqlite:
        raise HTTPException(status_code=501, detail="Members not supported in SQLite mode")

    role = await store.get_member_role(project_id, current_user.id)
    if role != "owner" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Project owner access required to remove other members")

    stmt = select(ProjectMember).where(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user_id
    )
    result = await session.execute(stmt)
    member = result.scalar_one_or_none()
    
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    await session.delete(member)
    await session.commit()
