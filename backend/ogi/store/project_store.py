from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, or_

from ogi.models import Project, ProjectCreate, ProjectUpdate, ProjectMember, ProjectBookmark, UserProfile


class ProjectStore:
    """Project CRUD – unified implementation using SQLModel and AsyncSession."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: ProjectCreate, owner_id: UUID) -> Project:
        project = Project(
            name=data.name,
            description=data.description,
            owner_id=owner_id,
            is_public=data.is_public,
        )
        self.session.add(project)
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def get(self, project_id: UUID) -> Project | None:
        project = await self.session.get(Project, project_id)
        return project

    async def list_all(self, user_id: UUID) -> list[Project]:
        stmt = (
            select(Project)
            .outerjoin(ProjectMember, Project.id == ProjectMember.project_id)
            .where(
                or_(
                    Project.owner_id == user_id,
                    Project.owner_id.is_(None),
                    Project.is_public == True,
                    ProjectMember.user_id == user_id,
                )
            )
            .order_by(Project.updated_at.desc())
            .distinct()
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_public(self, search: str | None = None) -> list[tuple[Project, str]]:
        """Return public projects with owner display_name. Returns list of (project, owner_name)."""
        stmt = (
            select(Project, UserProfile.display_name)
            .outerjoin(UserProfile, Project.owner_id == UserProfile.id)
            .where(Project.is_public == True)
            .order_by(Project.updated_at.desc())
        )
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Project.name.ilike(pattern),
                    Project.description.ilike(pattern),
                )
            )
        result = await self.session.execute(stmt)
        return [(row[0], row[1] or "") for row in result.all()]

    async def list_my_projects(self, user_id: UUID) -> list[dict]:
        """Return projects grouped by source: owned, member, bookmarked."""
        # Owned projects
        owned_stmt = select(Project).where(Project.owner_id == user_id).order_by(Project.updated_at.desc())
        owned_result = await self.session.execute(owned_stmt)
        owned = [{"project": p, "source": "owned", "role": "owner"} for p in owned_result.scalars().all()]

        # Member projects (not owned)
        member_stmt = (
            select(Project, ProjectMember.role)
            .join(ProjectMember, Project.id == ProjectMember.project_id)
            .where(ProjectMember.user_id == user_id)
            .where(Project.owner_id != user_id)
            .order_by(Project.updated_at.desc())
        )
        member_result = await self.session.execute(member_stmt)
        member = [{"project": row[0], "source": "member", "role": row[1]} for row in member_result.all()]

        # Bookmarked projects
        bookmark_stmt = (
            select(Project)
            .join(ProjectBookmark, Project.id == ProjectBookmark.project_id)
            .where(ProjectBookmark.user_id == user_id)
            .order_by(Project.updated_at.desc())
        )
        bookmark_result = await self.session.execute(bookmark_stmt)
        # Exclude projects already in owned or member
        owned_ids = {d["project"].id for d in owned}
        member_ids = {d["project"].id for d in member}
        bookmarked = [
            {"project": p, "source": "bookmarked", "role": "viewer"}
            for p in bookmark_result.scalars().all()
            if p.id not in owned_ids and p.id not in member_ids
        ]

        return owned + member + bookmarked

    async def update(self, project_id: UUID, data: ProjectUpdate) -> Project | None:
        project = await self.get(project_id)
        if project is None:
            return None

        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return project

        for key, value in update_data.items():
            setattr(project, key, value)
            
        project.updated_at = datetime.now(timezone.utc)
        self.session.add(project)
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def delete(self, project_id: UUID) -> bool:
        project = await self.get(project_id)
        if not project:
            return False
        
        await self.session.delete(project)
        await self.session.commit()
        return True

    async def get_member_role(self, project_id: UUID, user_id: UUID) -> str | None:
        project = await self.get(project_id)
        if not project:
            return None
            
        if project.owner_id == user_id or project.owner_id is None:
            return "owner"

        # Check for explicit membership role
        stmt = select(ProjectMember.role).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id
        )
        result = await self.session.execute(stmt)
        role = result.scalar_one_or_none()

        if role:
            return role

        if project.is_public:
            return "viewer"

        return None

    # --- Bookmarks ---

    async def add_bookmark(self, user_id: UUID, project_id: UUID) -> bool:
        """Bookmark a public project. Returns True if created, False if already exists."""
        existing = await self.session.get(ProjectBookmark, (user_id, project_id))
        if existing:
            return False
        bookmark = ProjectBookmark(user_id=user_id, project_id=project_id)
        self.session.add(bookmark)
        await self.session.commit()
        return True

    async def remove_bookmark(self, user_id: UUID, project_id: UUID) -> bool:
        """Remove a bookmark. Returns True if deleted."""
        bookmark = await self.session.get(ProjectBookmark, (user_id, project_id))
        if not bookmark:
            return False
        await self.session.delete(bookmark)
        await self.session.commit()
        return True

    async def get_bookmarked_ids(self, user_id: UUID) -> set[UUID]:
        """Return set of project IDs bookmarked by user."""
        stmt = select(ProjectBookmark.project_id).where(ProjectBookmark.user_id == user_id)
        result = await self.session.execute(stmt)
        return set(result.scalars().all())
