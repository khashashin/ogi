from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, or_

from ogi.models import Project, ProjectCreate, ProjectUpdate, ProjectMember


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
