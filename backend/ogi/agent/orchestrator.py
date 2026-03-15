from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from uuid import UUID

from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ogi.agent.models import (
    AgentEventMessage,
    AgentRun,
    AgentRunStatus,
    AgentStep,
    AgentStepStatus,
    AgentStepType,
)
from ogi.agent.store import AgentRunStore, AgentStepStore
from ogi.config import settings

logger = logging.getLogger("ogi.agent")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def publish_agent_event(redis_conn: Redis | None, message: AgentEventMessage) -> None:  # type: ignore[type-arg]
    if redis_conn is None:
        return
    redis_conn.publish(
        f"ogi:transform_events:{message.project_id}",
        message.model_dump_json(),
    )


def build_agent_event(
    *,
    event_type: str,
    run: AgentRun,
    step: AgentStep | None = None,
    summary: str | None = None,
) -> AgentEventMessage:
    return AgentEventMessage(
        type=event_type,
        project_id=run.project_id,
        run_id=run.id,
        step_id=None if step is None else step.id,
        status=run.status.value if step is None else step.status.value,
        summary=summary,
        timestamp=datetime.now(timezone.utc),
    )


class BudgetExceededError(RuntimeError):
    pass


@dataclass
class OrchestratorIterationResult:
    claimed_step_id: UUID | None = None
    processed: bool = False


class AgentOrchestrator:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        worker_id: str,
        redis_conn: Redis | None = None,  # type: ignore[type-arg]
        claim_timeout_seconds: int | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._worker_id = worker_id
        self._redis_conn = redis_conn
        self._claim_timeout_seconds = claim_timeout_seconds or settings.agent_claim_timeout_sec

    async def recover_stale_state(self) -> tuple[int, int]:
        async with self._session_factory() as session:
            step_store = AgentStepStore(session)
            run_store = AgentRunStore(session)
            recovered_steps = await step_store.recover_stale_claims(self._claim_timeout_seconds)
            recovered_runs = await run_store.recover_stale_runs(self._claim_timeout_seconds)
            return recovered_steps, recovered_runs

    async def run_once(self) -> OrchestratorIterationResult:
        async with self._session_factory() as session:
            step_store = AgentStepStore(session)
            claimed = await step_store.claim_next_runnable_step(
                self._worker_id,
                stale_after_seconds=self._claim_timeout_seconds,
            )
            if claimed is None:
                return OrchestratorIterationResult()
            step_id = claimed.id

        await self.process_step(step_id)
        return OrchestratorIterationResult(claimed_step_id=step_id, processed=True)

    async def process_step(self, step_id: UUID) -> None:
        async with self._session_factory() as session:
            run_store = AgentRunStore(session)
            step_store = AgentStepStore(session)

            step = await step_store.get(step_id)
            if step is None:
                return
            run = await run_store.get(step.run_id)
            if run is None:
                return

            if step.worker_id != self._worker_id or step.status != AgentStepStatus.RUNNING:
                return

            try:
                self._enforce_budgets(run, step)
                if run.status == AgentRunStatus.PENDING:
                    run.status = AgentRunStatus.RUNNING
                    run.updated_at = datetime.now(timezone.utc)
                    session.add(run)
                    await session.commit()
                    await session.refresh(run)

                await self._execute_claimed_step(session, run, step)
            except BudgetExceededError as exc:
                await self._fail_run(session, run, step, str(exc))
            except Exception as exc:
                logger.exception("Agent step %s failed", step.id)
                await self._fail_run(session, run, step, str(exc))

    def _enforce_budgets(self, run: AgentRun, step: AgentStep) -> None:
        budget = run.budget or {}
        usage = run.usage or {}

        max_steps = budget.get("max_steps")
        if max_steps is not None and int(usage.get("steps_used", 0)) >= int(max_steps):
            raise BudgetExceededError("AI Investigator max_steps budget exceeded")

        max_runtime_sec = budget.get("max_runtime_sec")
        if max_runtime_sec is not None:
            elapsed = (datetime.now(timezone.utc) - _as_utc(run.created_at)).total_seconds()
            if elapsed >= int(max_runtime_sec):
                raise BudgetExceededError("AI Investigator max_runtime_sec budget exceeded")

        max_transforms = budget.get("max_transforms")
        if (
            max_transforms is not None
            and step.tool_name == "run_transform"
            and int(usage.get("transforms_run", 0)) >= int(max_transforms)
        ):
            raise BudgetExceededError("AI Investigator max_transforms budget exceeded")

    async def _execute_claimed_step(
        self,
        session: AsyncSession,
        run: AgentRun,
        step: AgentStep,
    ) -> None:
        now = datetime.now(timezone.utc)
        run_store = AgentRunStore(session)

        if step.type == AgentStepType.APPROVAL_REQUEST:
            decision = (step.approval_payload or {}).get("decision")
            if decision == "approved":
                step.status = AgentStepStatus.COMPLETED
                step.completed_at = now
                self._increment_usage(run, step)
                session.add(step)
                session.add(run)
                await session.commit()
                await session.refresh(run)
                await session.refresh(step)
                publish_agent_event(
                    self._redis_conn,
                    build_agent_event(event_type="agent_approval_resolved", run=run, step=step),
                )
                return

            if decision == "rejected":
                run.status = AgentRunStatus.PAUSED
                run.updated_at = now
                session.add(run)
                await session.commit()
                await session.refresh(run)
                publish_agent_event(
                    self._redis_conn,
                    build_agent_event(event_type="agent_approval_resolved", run=run, step=step),
                )
                return

            if step.status == AgentStepStatus.RUNNING:
                step.status = AgentStepStatus.WAITING_APPROVAL
                step.approval_payload = step.approval_payload or {
                    "tool_name": step.tool_name,
                    "tool_input": step.tool_input or {},
                }
                step.worker_id = None
                step.claimed_at = None
                run.status = AgentRunStatus.PAUSED
                run.updated_at = now
                session.add(run)
                session.add(step)
                await session.commit()
                await session.refresh(run)
                await session.refresh(step)
                publish_agent_event(
                    self._redis_conn,
                    build_agent_event(event_type="agent_approval_requested", run=run, step=step),
                )
                return

        if step.type == AgentStepType.SUMMARY:
            step.status = AgentStepStatus.COMPLETED
            step.completed_at = now
            run.status = AgentRunStatus.COMPLETED
            run.summary = step.llm_output or (step.tool_output or {}).get("summary")
            run.completed_at = now
            self._increment_usage(run, step)
            session.add(step)
            session.add(run)
            await session.commit()
            await session.refresh(run)
            await session.refresh(step)
            publish_agent_event(
                self._redis_conn,
                build_agent_event(
                    event_type="agent_run_completed",
                    run=run,
                    step=step,
                    summary=run.summary,
                ),
            )
            return

        if step.type == AgentStepType.ERROR:
            await self._fail_run(
                session,
                run,
                step,
                step.llm_output or (step.tool_output or {}).get("error") or "Agent step failed",
            )
            return

        step.status = AgentStepStatus.COMPLETED
        step.completed_at = now
        self._increment_usage(run, step)
        session.add(step)
        session.add(run)
        await session.commit()
        await session.refresh(run)
        await session.refresh(step)

        event_type = self._event_type_for_step(run, step)
        if event_type is not None:
            publish_agent_event(
                self._redis_conn,
                build_agent_event(event_type=event_type, run=run, step=step),
            )

        await run_store.save(run)

    async def _fail_run(
        self,
        session: AsyncSession,
        run: AgentRun,
        step: AgentStep,
        error_message: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        step.status = AgentStepStatus.FAILED
        step.completed_at = now
        run.status = AgentRunStatus.FAILED
        run.error = error_message
        run.completed_at = now
        session.add(step)
        session.add(run)
        await session.commit()
        await session.refresh(run)
        await session.refresh(step)
        publish_agent_event(
            self._redis_conn,
            build_agent_event(
                event_type="agent_run_failed",
                run=run,
                step=step,
                summary=error_message,
            ),
        )

    def _increment_usage(self, run: AgentRun, step: AgentStep) -> None:
        usage = dict(run.usage or {})
        usage["steps_used"] = int(usage.get("steps_used", 0)) + 1
        if step.type == AgentStepType.TOOL_CALL and step.tool_name == "run_transform":
            usage["transforms_run"] = int(usage.get("transforms_run", 0)) + 1
        run.usage = usage
        run.updated_at = datetime.now(timezone.utc)

    @staticmethod
    def _event_type_for_step(run: AgentRun, step: AgentStep) -> str | None:
        if step.type == AgentStepType.THINK:
            return None
        if step.type == AgentStepType.TOOL_CALL:
            return "agent_tool_called"
        if step.type == AgentStepType.TOOL_RESULT:
            return "agent_tool_result"
        if step.type == AgentStepType.APPROVAL_REQUEST and step.status == AgentStepStatus.COMPLETED:
            return "agent_approval_resolved"
        if run.status == AgentRunStatus.CANCELLED:
            return "agent_run_cancelled"
        return None


async def poll_orchestrator(
    *,
    orchestrator_factory: Callable[[], AgentOrchestrator],
    stop_event: asyncio.Event | None = None,
) -> None:
    stop_event = stop_event or asyncio.Event()
    orchestrator = orchestrator_factory()
    await orchestrator.recover_stale_state()

    while not stop_event.is_set():
        result = await orchestrator.run_once()
        if not result.processed:
            await asyncio.sleep(settings.agent_worker_poll_interval_sec)
