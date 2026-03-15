from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from uuid import UUID

from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ogi.agent.context import AgentContextBuilder
from ogi.agent.llm_provider import LLMProvider
from ogi.agent.models import (
    AgentEventMessage,
    AgentRun,
    AgentRunStatus,
    AgentStep,
    AgentStepStatus,
    AgentStepType,
    ScopeConfig,
)
from ogi.agent.store import AgentRunStore, AgentStepStore
from ogi.agent.tools import ToolContext, ToolRegistry
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
        llm_provider: LLMProvider,
        tool_registry: ToolRegistry,
        context_builder: AgentContextBuilder,
        redis_conn: Redis | None = None,  # type: ignore[type-arg]
        claim_timeout_seconds: int | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._worker_id = worker_id
        self._llm_provider = llm_provider
        self._tool_registry = tool_registry
        self._context_builder = context_builder
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
        if step.type == AgentStepType.THINK:
            await self._execute_think_step(session, run, step)
            return
        if step.type == AgentStepType.TOOL_CALL:
            await self._execute_tool_call_step(session, run, step)
            return

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
            return "agent_thinking"
        if step.type == AgentStepType.TOOL_CALL:
            return "agent_tool_called"
        if step.type == AgentStepType.TOOL_RESULT:
            return "agent_tool_result"
        if step.type == AgentStepType.APPROVAL_REQUEST and step.status == AgentStepStatus.COMPLETED:
            return "agent_approval_resolved"
        if run.status == AgentRunStatus.CANCELLED:
            return "agent_run_cancelled"
        return None

    async def _execute_think_step(
        self,
        session: AsyncSession,
        run: AgentRun,
        step: AgentStep,
    ) -> None:
        step_store = AgentStepStore(session)
        steps = await step_store.list_for_run(run.id)
        prior_steps = [item for item in steps if item.id != step.id]
        messages = await self._context_builder.build_messages(
            run=run,
            recent_steps=prior_steps,
            tools=self._tool_registry.list_tools(),
            session=session,
        )
        decision = await self._llm_provider.decide(messages=messages, tools=self._tool_registry.list_tools())

        now = datetime.now(timezone.utc)
        step.llm_output = decision.reasoning
        step.token_usage = decision.token_usage.model_dump(mode="json")
        step.status = AgentStepStatus.COMPLETED
        step.completed_at = now
        self._increment_usage(run, step)
        self._increment_llm_usage(run, decision.token_usage.prompt_tokens, decision.token_usage.completion_tokens)
        session.add(step)
        session.add(run)
        await session.commit()
        await session.refresh(step)
        await session.refresh(run)
        publish_agent_event(
            self._redis_conn,
            build_agent_event(event_type="agent_thinking", run=run, step=step, summary=decision.reasoning),
        )

        next_step_number = await step_store.next_step_number(run.id)
        if decision.action_type == "finish":
            summary_step = AgentStep(
                run_id=run.id,
                step_number=next_step_number,
                type=AgentStepType.SUMMARY,
                llm_output=decision.final_summary or decision.reasoning,
                status=AgentStepStatus.PENDING,
            )
            await step_store.create(summary_step)
            return

        if decision.action_type != "tool_call" or not decision.tool_name:
            raise RuntimeError("LLM decision did not produce a valid tool call or finish action")

        tool = self._tool_registry.get_tool(decision.tool_name)
        if tool is None:
            raise RuntimeError(f"LLM selected unknown tool '{decision.tool_name}'")

        tool_step = AgentStep(
            run_id=run.id,
            step_number=next_step_number,
            type=AgentStepType.TOOL_CALL,
            tool_name=decision.tool_name,
            tool_input=decision.tool_params,
            status=AgentStepStatus.PENDING,
            approval_payload={"requires_approval": tool.definition.requires_approval},
        )
        await step_store.create(tool_step)

    async def _execute_tool_call_step(
        self,
        session: AsyncSession,
        run: AgentRun,
        step: AgentStep,
    ) -> None:
        tool = self._tool_registry.get_tool(step.tool_name or "")
        if tool is None:
            raise RuntimeError(f"Unknown tool '{step.tool_name}'")

        now = datetime.now(timezone.utc)
        if tool.definition.requires_approval and step.status == AgentStepStatus.RUNNING:
            if (step.approval_payload or {}).get("decision") == "approved":
                pass
            elif (step.approval_payload or {}).get("decision") == "rejected":
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
            elif step.status == AgentStepStatus.RUNNING:
                step.status = AgentStepStatus.WAITING_APPROVAL
                step.worker_id = None
                step.claimed_at = None
                payload = dict(step.approval_payload or {})
                payload.update(
                    {
                        "tool_name": step.tool_name,
                        "tool_input": step.tool_input or {},
                        "requires_approval": True,
                    }
                )
                step.approval_payload = payload
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

        ctx = ToolContext(
            project_id=run.project_id,
            user_id=run.user_id,
            run_id=run.id,
            scope=ScopeConfig.model_validate(run.scope),
            session=session,
        )
        result = await self._tool_registry.execute(step.tool_name or "", step.tool_input or {}, ctx)

        step.status = AgentStepStatus.COMPLETED
        step.completed_at = now
        self._increment_usage(run, step)
        session.add(step)
        session.add(run)
        await session.commit()
        await session.refresh(step)
        await session.refresh(run)
        publish_agent_event(
            self._redis_conn,
            build_agent_event(event_type="agent_tool_called", run=run, step=step),
        )

        step_store = AgentStepStore(session)
        result_step = AgentStep(
            run_id=run.id,
            step_number=await step_store.next_step_number(run.id),
            type=AgentStepType.TOOL_RESULT,
            tool_name=step.tool_name,
            tool_input=step.tool_input,
            tool_output=result.model_dump(mode="json"),
            status=AgentStepStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
        )
        await step_store.create(result_step)
        publish_agent_event(
            self._redis_conn,
            build_agent_event(event_type="agent_tool_result", run=run, step=result_step, summary=result.summary),
        )

        next_think = AgentStep(
            run_id=run.id,
            step_number=await step_store.next_step_number(run.id),
            type=AgentStepType.THINK,
            status=AgentStepStatus.PENDING,
        )
        await step_store.create(next_think)

    def _increment_llm_usage(self, run: AgentRun, prompt_tokens: int, completion_tokens: int) -> None:
        usage = dict(run.usage or {})
        usage["llm_calls"] = int(usage.get("llm_calls", 0)) + 1
        usage["prompt_tokens"] = int(usage.get("prompt_tokens", 0)) + int(prompt_tokens)
        usage["completion_tokens"] = int(usage.get("completion_tokens", 0)) + int(completion_tokens)
        run.usage = usage
        run.updated_at = datetime.now(timezone.utc)


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
