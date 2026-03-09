from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from ogi.models import TransformRun


class TransformRunStore:
    """Transform run persistence – unified implementation using SQLModel and AsyncSession."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, run: TransformRun) -> TransformRun:
        # Check if exists (upsert logic)
        existing = await self.session.get(TransformRun, run.id)
        if existing:
            update_data = run.model_dump(exclude_unset=True)
            for k, v in update_data.items():
                setattr(existing, k, v)
            self.session.add(existing)
            await self.session.commit()
            await self.session.refresh(existing)
            return existing
        else:
            self.session.add(run)
            await self.session.commit()
            await self.session.refresh(run)
            return run

    async def get(self, run_id: UUID) -> TransformRun | None:
        return await self.session.get(TransformRun, run_id)

    async def list_by_project(self, project_id: UUID) -> list[TransformRun]:
        stmt = select(TransformRun).where(TransformRun.project_id == project_id).order_by(TransformRun.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
