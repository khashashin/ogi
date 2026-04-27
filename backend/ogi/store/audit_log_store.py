from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from ogi.models import AuditLog, AuditLogCreate


class AuditLogStore:
    """Audit log persistence for project-scoped action history."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        project_id: UUID,
        actor_user_id: UUID | None,
        data: AuditLogCreate,
    ) -> AuditLog:
        row = AuditLog(
            project_id=project_id,
            actor_user_id=actor_user_id,
            action=data.action,
            resource_type=data.resource_type,
            resource_id=data.resource_id,
            details=data.details,
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def list_by_project(self, project_id: UUID, limit: int = 200) -> list[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.project_id == project_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
