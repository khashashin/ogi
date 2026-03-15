from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ogi.agent.models import AgentRun, AgentStep
from ogi.agent.tools import ToolDefinition
from ogi.store.entity_store import EntityStore


@dataclass
class AgentContextBuilder:
    max_recent_steps: int = 8
    max_scope_entities: int = 25

    async def build_messages(
        self,
        *,
        run: AgentRun,
        recent_steps: list[AgentStep],
        tools: list[ToolDefinition],
        session: AsyncSession,
    ) -> list[dict[str, str]]:
        entity_store = EntityStore(session)
        scope_summary = await self._build_scope_summary(run, entity_store)
        older_steps = recent_steps[:-self.max_recent_steps]
        detailed_steps = recent_steps[-self.max_recent_steps :]

        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "You are OGI AI Investigator. Decide the next best investigative action. "
                    "Use only the available tools. Keep reasoning concise, factual, and auditable. "
                    "Do not invent entities or transform results."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Investigation goal:\n{run.prompt}\n\n"
                    f"Scope:\n{scope_summary}\n\n"
                    f"Available tools:\n{self._format_tools(tools)}"
                ),
            },
        ]

        if older_steps:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        f"Earlier completed steps summary:\n{self._summarize_steps(older_steps)}"
                    ),
                }
            )

        if detailed_steps:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        f"Recent step history:\n{self._render_recent_steps(detailed_steps)}"
                    ),
                }
            )

        return messages

    async def _build_scope_summary(self, run: AgentRun, entity_store: EntityStore) -> str:
        if run.scope.get("mode") == "selected":
            entity_ids = [UUID(value) if isinstance(value, str) else value for value in run.scope.get("entity_ids", [])]
            entities = []
            for entity_id in entity_ids[: self.max_scope_entities]:
                entity = await entity_store.get(entity_id)
                if entity is not None:
                    entities.append(f"- {entity.value} ({entity.type.value})")
            return "Selected entities:\n" + ("\n".join(entities) if entities else "- none")

        entities = await entity_store.list_by_project(run.project_id, limit=self.max_scope_entities)
        preview = "\n".join(f"- {entity.value} ({entity.type.value})" for entity in entities[: self.max_scope_entities])
        suffix = "" if len(entities) < self.max_scope_entities else "\n- ..."
        return f"Whole project scope. Current entity preview:\n{preview or '- none'}{suffix}"

    @staticmethod
    def _format_tools(tools: list[ToolDefinition]) -> str:
        lines: list[str] = []
        for tool in tools:
            approval = " approval-required" if tool.requires_approval else ""
            lines.append(f"- {tool.name} [{tool.risk_level}{approval}]: {tool.description}")
        return "\n".join(lines)

    @staticmethod
    def _summarize_steps(steps: list[AgentStep]) -> str:
        return "\n".join(
            f"- step {step.step_number}: {step.type.value} ({step.status.value})"
            for step in steps
        )

    @staticmethod
    def _render_recent_steps(steps: list[AgentStep]) -> str:
        rendered: list[str] = []
        for step in steps:
            line = f"- step {step.step_number}: {step.type.value} [{step.status.value}]"
            if step.tool_name:
                line += f" tool={step.tool_name}"
            if step.llm_output:
                line += f" reasoning={step.llm_output[:400]}"
            if step.tool_output:
                line += f" output={str(step.tool_output)[:500]}"
            rendered.append(line)
        return "\n".join(rendered)
