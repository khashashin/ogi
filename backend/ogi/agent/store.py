from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, exists, func, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from ogi.agent.models import AgentRun, AgentRunStatus, AgentStep, AgentStepStatus


ACTIVE_RUN_STATUSES = (
    AgentRunStatus.PENDING,
    AgentRunStatus.RUNNING,
    AgentRunStatus.PAUSED,
)
RUNNABLE_RUN_STATUSES = (
    AgentRunStatus.PENDING,
    AgentRunStatus.RUNNING,
)
CLAIMABLE_STEP_STATUSES = (
    AgentStepStatus.PENDING,
    AgentStepStatus.APPROVED,
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

    async def recover_stale_runs(self, timeout_seconds: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=timeout_seconds)

        active_step_exists = (
            select(AgentStep.id)
            .where(AgentStep.run_id == AgentRun.id)
            .where(
                AgentStep.status.in_(
                    (
                        AgentStepStatus.PENDING,
                        AgentStepStatus.RUNNING,
                        AgentStepStatus.APPROVED,
                        AgentStepStatus.WAITING_APPROVAL,
                    )
                )
            )
            .limit(1)
        )

        stmt = (
            select(AgentRun)
            .where(AgentRun.status == AgentRunStatus.RUNNING)
            .where(AgentRun.updated_at < cutoff)
            .where(~exists(active_step_exists))
        )
        result = await self.session.execute(stmt)
        stale_runs = list(result.scalars().all())
        now = datetime.now(timezone.utc)
        for run in stale_runs:
            run.status = AgentRunStatus.FAILED
            run.error = "Agent worker stalled and no runnable steps remained"
            run.completed_at = now
            run.updated_at = now
            self.session.add(run)

        if stale_runs:
            await self.session.commit()
        return len(stale_runs)


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

    async def claim_next_runnable_step(
        self,
        worker_id: str,
        stale_after_seconds: int,
    ) -> AgentStep | None:
        now = datetime.now(timezone.utc)
        stale_cutoff = now - timedelta(seconds=stale_after_seconds)

        claimable_step_id = (
            select(AgentStep.id)
            .join(AgentRun, AgentRun.id == AgentStep.run_id)
            .where(AgentRun.status.in_(RUNNABLE_RUN_STATUSES))
            .where(
                or_(
                    AgentStep.status.in_(CLAIMABLE_STEP_STATUSES),
                    and_(
                        AgentStep.status == AgentStepStatus.RUNNING,
                        AgentStep.claimed_at.is_not(None),
                        AgentStep.claimed_at < stale_cutoff,
                    ),
                )
            )
            .order_by(AgentStep.created_at.asc(), AgentStep.step_number.asc())
            .limit(1)
            .scalar_subquery()
        )

        stmt = (
            update(AgentStep)
            .where(AgentStep.id == claimable_step_id)
            .values(
                status=AgentStepStatus.RUNNING,
                worker_id=worker_id,
                claimed_at=now,
            )
            .returning(AgentStep)
        )
        result = await self.session.execute(stmt)
        claimed = result.scalar_one_or_none()
        if claimed is None:
            await self.session.rollback()
            return None

        await self.session.commit()
        return claimed

    async def recover_stale_claims(self, timeout_seconds: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=timeout_seconds)
        stmt = (
            update(AgentStep)
            .where(AgentStep.status == AgentStepStatus.RUNNING)
            .where(AgentStep.claimed_at.is_not(None))
            .where(AgentStep.claimed_at < cutoff)
            .values(
                status=AgentStepStatus.PENDING,
                worker_id=None,
                claimed_at=None,
            )
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return int(result.rowcount or 0)

    async def has_unfinished_steps(self, run_id: UUID) -> bool:
        stmt = (
            select(func.count())
            .select_from(AgentStep)
            .where(AgentStep.run_id == run_id)
            .where(
                AgentStep.status.in_(
                    (
                        AgentStepStatus.PENDING,
                        AgentStepStatus.RUNNING,
                        AgentStepStatus.WAITING_APPROVAL,
                        AgentStepStatus.APPROVED,
                    )
                )
            )
        )
        result = await self.session.execute(stmt)
        return bool(result.scalar_one())
