from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable
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


def _enum_value(value: object) -> str:
    return value.value if hasattr(value, "value") else str(value)


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
        status=_enum_value(run.status if step is None else step.status),
        summary=summary,
        timestamp=datetime.now(timezone.utc),
    )


class BudgetExceededError(RuntimeError):
    pass


class AgentLoopDetectedError(RuntimeError):
    pass


@dataclass(frozen=True)
class ActionPolicyDecision:
    mode: str
    message: str | None = None


@dataclass
class OrchestratorIterationResult:
    claimed_step_id: UUID | None = None
    processed: bool = False


class AgentOrchestrator:
    READ_ONLY_TOOLS = {"list_entities", "get_entity", "list_transforms", "search_graph"}
    DUPLICATE_READ_REPLAN_LIMIT = 3
    KNOWN_GRAPH_ITEM_LIMIT = 500
    TRANSFORM_MEMORY_LIMIT = 24
    EXHAUSTED_FAMILY_RECENT_LOW_YIELD_THRESHOLD = 2
    EXHAUSTED_FAMILY_MIN_RUNS = 3

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        worker_id: str,
        llm_provider_factory: Callable[[AsyncSession, AgentRun], Awaitable[LLMProvider]],
        tool_registry: ToolRegistry,
        context_builder: AgentContextBuilder,
        redis_conn: Redis | None = None,  # type: ignore[type-arg]
        claim_timeout_seconds: int | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._worker_id = worker_id
        self._llm_provider_factory = llm_provider_factory
        self._tool_registry = tool_registry
        self._context_builder = context_builder
        self._redis_conn = redis_conn
        self._claim_timeout_seconds = claim_timeout_seconds or settings.agent_claim_timeout_sec

    @staticmethod
    def _normalize_tool_input(params: dict | None) -> str:
        normalized = params or {}
        return json.dumps(normalized, sort_keys=True, separators=(",", ":"), default=str)

    @classmethod
    def _tool_signature(cls, tool_name: str | None, params: dict | None) -> str:
        return f"{tool_name or ''}:{cls._normalize_tool_input(params)}"

    @classmethod
    def _transform_signature(cls, params: dict | None) -> str:
        params = params or {}
        normalized = {
            "entity_id": str(params.get("entity_id") or ""),
            "entity_value": str(params.get("entity_value") or ""),
            "transform_name": str(params.get("transform_name") or ""),
            "config": params.get("config") or {},
        }
        return cls._normalize_tool_input(normalized)

    def _check_action_policy(
        self,
        *,
        run: AgentRun,
        prior_steps: list[AgentStep],
        tool_name: str,
        tool_params: dict | None,
    ) -> ActionPolicyDecision:
        if tool_name == "finish_investigation":
            return ActionPolicyDecision(mode="allow")

        tool_signature = self._tool_signature(tool_name, tool_params)
        completed_matching = [
            step
            for step in prior_steps
            if step.type == AgentStepType.TOOL_CALL
            and step.status == AgentStepStatus.COMPLETED
            and self._tool_signature(step.tool_name, step.tool_input) == tool_signature
        ]
        if completed_matching and tool_name == "run_transform":
            params = tool_params or {}
            transform_name = params.get("transform_name") or "unknown"
            target = params.get("entity_id") or params.get("entity_value") or "unknown"
            return ActionPolicyDecision(
                mode="fail",
                message=(
                    f"AI Investigator loop detected: transform '{transform_name}' already ran on '{target}' in this run"
                ),
            )

        if tool_name == "run_transform":
            params = tool_params or {}
            transform_name = str(params.get("transform_name") or "").strip()
            exhausted_families = {
                str(item).strip()
                for item in (run.config or {}).get("exhausted_transform_families", [])
                if str(item).strip()
            }
            if transform_name and transform_name in exhausted_families:
                return ActionPolicyDecision(
                    mode="replan",
                    message=(
                        f"Policy feedback: transform family '{transform_name}' has been low-yield in recent runs. "
                        "Choose a different transform family, deepen an existing pivot, or finish the investigation."
                    ),
                )

        if completed_matching and tool_name in self.READ_ONLY_TOOLS:
            return ActionPolicyDecision(
                mode="replan",
                message=(
                    f"Policy feedback: tool '{tool_name}' with these inputs was already executed earlier in this run. "
                    "Use the existing results, choose a different pivot, or finish the investigation."
                ),
            )

        if len(completed_matching) >= 2:
            if tool_name in self.READ_ONLY_TOOLS:
                return ActionPolicyDecision(
                    mode="replan",
                    message=(
                        f"Policy feedback: tool '{tool_name}' with these inputs was already executed multiple times. "
                        "Choose a different entity, a different transform, or finish the investigation."
                    ),
                )
            return ActionPolicyDecision(
                mode="fail",
                message=(
                    f"AI Investigator loop detected: tool '{tool_name}' with the same inputs has already been executed multiple times"
                ),
            )

        recent_tool_calls = [
            step for step in prior_steps if step.type == AgentStepType.TOOL_CALL and step.status == AgentStepStatus.COMPLETED
        ][-6:]
        recent_signatures = [self._tool_signature(step.tool_name, step.tool_input) for step in recent_tool_calls]
        if recent_signatures.count(tool_signature) >= 2:
            if tool_name in self.READ_ONLY_TOOLS:
                return ActionPolicyDecision(
                    mode="replan",
                    message=(
                        f"Policy feedback: repeated recent action '{tool_name}' with the same inputs was already attempted. "
                        "Use the existing results, pick a new pivot, or finish."
                    ),
                )
            return ActionPolicyDecision(
                mode="fail",
                message=f"AI Investigator loop detected: repeated recent action '{tool_name}' with the same inputs",
            )

        return ActionPolicyDecision(mode="allow")

    @staticmethod
    def _append_policy_feedback(run: AgentRun, message: str) -> None:
        config = dict(run.config or {})
        feedback = list(config.get("policy_feedback") or [])
        feedback.append(message)
        config["policy_feedback"] = feedback[-3:]
        run.config = config

    @staticmethod
    def _clear_policy_feedback(run: AgentRun) -> None:
        config = dict(run.config or {})
        if "policy_feedback" in config:
            config.pop("policy_feedback", None)
            run.config = config

    def _register_duplicate_read_replan(self, run: AgentRun, message: str) -> None:
        usage = dict(run.usage or {})
        count = int(usage.get("duplicate_read_replans", 0)) + 1
        usage["duplicate_read_replans"] = count
        run.usage = usage
        self._append_policy_feedback(run, message)
        if count >= self.DUPLICATE_READ_REPLAN_LIMIT:
            raise AgentLoopDetectedError(
                "AI Investigator loop detected: repeated duplicate read-only actions after policy feedback"
            )

    @staticmethod
    def _edge_signature(edge: dict[str, object]) -> str:
        return "|".join(
            [
                str(edge.get("source_id") or ""),
                str(edge.get("target_id") or ""),
                str(edge.get("label") or ""),
                str(edge.get("source_transform") or ""),
            ]
        )

    def _record_transform_outcome(self, run: AgentRun, step: AgentStep, result: object) -> None:
        if step.tool_name != "run_transform":
            return
        if not isinstance(result, dict):
            return

        result_payload = result.get("result")
        if not isinstance(result_payload, dict):
            return

        config = dict(run.config or {})
        known_entity_ids = {
            str(item)
            for item in config.get("known_entity_ids", [])
            if str(item).strip()
        }
        known_edge_signatures = {
            str(item)
            for item in config.get("known_edge_signatures", [])
            if str(item).strip()
        }

        entities = result_payload.get("entities")
        edges = result_payload.get("edges")
        entity_items = entities if isinstance(entities, list) else []
        edge_items = edges if isinstance(edges, list) else []

        new_entity_ids: set[str] = set()
        new_entity_types: set[str] = set()
        for item in entity_items:
            if not isinstance(item, dict):
                continue
            entity_id = str(item.get("id") or "").strip()
            if not entity_id:
                continue
            if entity_id not in known_entity_ids:
                new_entity_ids.add(entity_id)
                entity_type = str(item.get("type") or "").strip()
                if entity_type:
                    new_entity_types.add(entity_type)
            known_entity_ids.add(entity_id)

        new_edge_signatures: set[str] = set()
        for item in edge_items:
            if not isinstance(item, dict):
                continue
            signature = self._edge_signature(item)
            if not signature.strip():
                continue
            if signature not in known_edge_signatures:
                new_edge_signatures.add(signature)
            known_edge_signatures.add(signature)

        params = step.tool_input or {}
        transform_name = str(params.get("transform_name") or "").strip() or "unknown"
        target = str(params.get("entity_id") or params.get("entity_value") or "").strip() or "unknown"
        low_yield = (
            len(new_entity_ids) == 0 and len(new_edge_signatures) == 0
        ) or (
            len(new_entity_ids) <= 1 and len(new_edge_signatures) <= 1 and len(new_entity_types) <= 1
        )

        memory = list(config.get("transform_memory") or [])
        memory.append(
            {
                "transform_name": transform_name,
                "target": target,
                "new_entity_count": len(new_entity_ids),
                "new_edge_count": len(new_edge_signatures),
                "new_entity_types": sorted(new_entity_types),
                "low_yield": low_yield,
            }
        )
        memory = memory[-self.TRANSFORM_MEMORY_LIMIT :]

        family_history = [
            item for item in memory
            if isinstance(item, dict) and str(item.get("transform_name") or "").strip() == transform_name
        ]
        recent_family_history = family_history[-3:]
        family_stats = dict(config.get("transform_family_stats") or {})
        family_stats[transform_name] = {
            "runs": len(family_history),
            "recent_low_yield_runs": sum(1 for item in recent_family_history if bool(item.get("low_yield"))),
            "recent_targets": [
                str(item.get("target") or "")
                for item in family_history[-5:]
                if str(item.get("target") or "").strip()
            ],
        }

        exhausted_families = [
            str(item).strip()
            for item in config.get("exhausted_transform_families", [])
            if str(item).strip()
        ]
        stats = family_stats[transform_name]
        if (
            stats["runs"] >= self.EXHAUSTED_FAMILY_MIN_RUNS
            and stats["recent_low_yield_runs"] >= self.EXHAUSTED_FAMILY_RECENT_LOW_YIELD_THRESHOLD
            and transform_name not in exhausted_families
        ):
            exhausted_families.append(transform_name)

        config["known_entity_ids"] = list(sorted(known_entity_ids))[-self.KNOWN_GRAPH_ITEM_LIMIT :]
        config["known_edge_signatures"] = list(sorted(known_edge_signatures))[-self.KNOWN_GRAPH_ITEM_LIMIT :]
        config["transform_memory"] = memory
        config["transform_family_stats"] = family_stats
        config["exhausted_transform_families"] = exhausted_families[-10:]
        run.config = config
        run.updated_at = datetime.now(timezone.utc)

    @staticmethod
    def _reset_duplicate_read_replans(run: AgentRun) -> None:
        usage = dict(run.usage or {})
        if usage.get("duplicate_read_replans"):
            usage["duplicate_read_replans"] = 0
            run.usage = usage

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
            except (BudgetExceededError, AgentLoopDetectedError) as exc:
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
        llm_provider = await self._llm_provider_factory(session, run)
        decision = await llm_provider.decide(messages=messages, tools=self._tool_registry.list_tools())

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
            self._clear_policy_feedback(run)
            self._reset_duplicate_read_replans(run)
            session.add(run)
            await session.commit()
            await session.refresh(run)
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

        policy = self._check_action_policy(
            run=run,
            prior_steps=prior_steps,
            tool_name=decision.tool_name,
            tool_params=decision.tool_params,
        )
        if policy.message:
            step.llm_output = f"{decision.reasoning}\n\n{policy.message}"
            session.add(step)
            await session.commit()
            await session.refresh(step)

        if policy.mode == "replan":
            assert policy.message is not None
            self._register_duplicate_read_replan(run, policy.message)
            run.updated_at = datetime.now(timezone.utc)
            session.add(run)
            await session.commit()
            await session.refresh(run)
            await step_store.create(
                AgentStep(
                    run_id=run.id,
                    step_number=next_step_number,
                    type=AgentStepType.THINK,
                    status=AgentStepStatus.PENDING,
                )
            )
            return

        if policy.mode == "fail":
            assert policy.message is not None
            raise AgentLoopDetectedError(policy.message)

        self._clear_policy_feedback(run)
        self._reset_duplicate_read_replans(run)
        run.updated_at = datetime.now(timezone.utc)
        session.add(run)
        await session.commit()
        await session.refresh(run)

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

        step_store = AgentStepStore(session)
        prior_steps = [item for item in await step_store.list_for_run(run.id) if item.id != step.id]
        policy = self._check_action_policy(
            run=run,
            prior_steps=prior_steps,
            tool_name=step.tool_name or "",
            tool_params=step.tool_input,
        )
        if policy.mode != "allow":
            raise AgentLoopDetectedError(policy.message or "AI Investigator loop detected")

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
        self._record_transform_outcome(run, step, result.data)

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
