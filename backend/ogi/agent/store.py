from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from ogi.agent.models import AgentRun, AgentRunStatus, AgentStep


ACTIVE_RUN_STATUSES = (
    AgentRunStatus.PENDING,
    AgentRunStatus.RUNNING,
    AgentRunStatus.PAUSED,
)


class AgentRunStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, run: AgentRun) -> AgentRun:
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def get(self, run_id: UUID) -> AgentRun | None:
        return await self.session.get(AgentRun, run_id)

    async def save(self, run: AgentRun) -> AgentRun:
        existing = await self.session.get(AgentRun, run.id)
        if existing is not None:
            update_data = run.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(existing, key, value)
            existing.updated_at = datetime.now(timezone.utc)
            self.session.add(existing)
            await self.session.commit()
            await self.session.refresh(existing)
            return existing

        run.updated_at = datetime.now(timezone.utc)
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def list_by_project(
        self,
        project_id: UUID,
        statuses: list[AgentRunStatus] | None = None,
        limit: int = 200,
    ) -> list[AgentRun]:
        stmt = (
            select(AgentRun)
            .where(AgentRun.project_id == project_id)
            .order_by(AgentRun.created_at.desc())
            .limit(limit)
        )
        if statuses:
            stmt = stmt.where(AgentRun.status.in_(statuses))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_for_project(self, project_id: UUID) -> AgentRun | None:
        stmt = (
            select(AgentRun)
            .where(AgentRun.project_id == project_id)
            .where(AgentRun.status.in_(ACTIVE_RUN_STATUSES))
            .order_by(AgentRun.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class AgentStepStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, step: AgentStep) -> AgentStep:
        self.session.add(step)
        await self.session.commit()
        await self.session.refresh(step)
        return step

    async def get(self, step_id: UUID) -> AgentStep | None:
        return await self.session.get(AgentStep, step_id)

    async def save(self, step: AgentStep) -> AgentStep:
        existing = await self.session.get(AgentStep, step.id)
        if existing is not None:
            update_data = step.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(existing, key, value)
            self.session.add(existing)
            await self.session.commit()
            await self.session.refresh(existing)
            return existing

        self.session.add(step)
        await self.session.commit()
        await self.session.refresh(step)
        return step

    async def list_for_run(self, run_id: UUID) -> list[AgentStep]:
        stmt = (
            select(AgentStep)
            .where(AgentStep.run_id == run_id)
            .order_by(AgentStep.step_number.asc(), AgentStep.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def next_step_number(self, run_id: UUID) -> int:
        steps = await self.list_for_run(run_id)
        if not steps:
            return 1
        return max(step.step_number for step in steps) + 1
