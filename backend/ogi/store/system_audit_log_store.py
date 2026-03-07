from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from ogi.models import SystemAuditLog, SystemAuditLogCreate


class SystemAuditLogStore:
    """Persistence for global, non-project-scoped audit events."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        actor_user_id: UUID | None,
        data: SystemAuditLogCreate,
    ) -> SystemAuditLog:
        row = SystemAuditLog(
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

    async def list_recent(self, limit: int = 200) -> list[SystemAuditLog]:
        stmt = select(SystemAuditLog).order_by(SystemAuditLog.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
