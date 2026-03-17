from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ogi.agent.models import AgentRun, AgentStep
from ogi.agent.project_memory_store import AgentProjectMemoryStore
from ogi.agent.tools import ToolDefinition
from ogi.store.entity_store import EntityStore


@dataclass
class AgentContextBuilder:
    max_recent_steps: int = 8
    max_scope_entities: int = 25
    PLATFORM_KEYWORDS = (
        "youtube",
        "github",
        "reddit",
        "twitter",
        "x.com",
        "instagram",
        "tiktok",
        "linkedin",
        "facebook",
        "telegram",
        "discord",
        "twitch",
    )

    async def build_messages(
        self,
        *,
        run: AgentRun,
        recent_steps: list[AgentStep],
        tools: list[ToolDefinition],
        session: AsyncSession,
    ) -> list[dict[str, str]]:
        entity_store = EntityStore(session)
        project_memory_store = AgentProjectMemoryStore(session)
        scope_summary = await self._build_scope_summary(run, entity_store)
        project_memory = await project_memory_store.build_read_model(run.project_id)
        older_steps = recent_steps[:-self.max_recent_steps]
        detailed_steps = recent_steps[-self.max_recent_steps :]

        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "You are OGI AI Investigator. Decide the next best investigative action. "
                    "Use only the available tools. Keep reasoning concise, factual, and auditable. "
                    "Do not invent entities or transform results. "
                    "Entity properties are metadata, not standalone graph entities, unless they are separately "
                    "returned by search/list tools or explicitly created with create_entity."
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

        goal_focus = self._render_goal_focus(run.prompt)
        if goal_focus:
            messages.append({"role": "system", "content": goal_focus})

        if project_memory.summary or project_memory.known_facts or project_memory.recent_runs:
            messages.append(
                {
                    "role": "system",
                    "content": self._render_project_memory(project_memory),
                }
            )

        resume_context = self._render_resume_context(run)
        if resume_context:
            messages.append({"role": "system", "content": resume_context})

        if older_steps:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        f"Earlier completed steps summary:\n{self._summarize_steps(older_steps)}"
                    ),
                }
            )

        attempted_actions = self._summarize_attempted_actions(recent_steps)
        if attempted_actions:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "Previously attempted actions and outcomes:\n"
                        f"{attempted_actions}\n\n"
                        "Do not repeat the same tool call or rerun the same transform on the same entity "
                        "unless there is new evidence."
                    ),
                }
            )

        policy_feedback = self._summarize_policy_feedback(run)
        if policy_feedback:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "Policy feedback from recent validation:\n"
                        f"{policy_feedback}\n\n"
                        "Use the already collected results. Do not repeat blocked read-only actions."
                    ),
                }
            )

        transform_progress = self._summarize_transform_progress(run)
        if transform_progress:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "Recent transform novelty and exhausted paths:\n"
                        f"{transform_progress}\n\n"
                        "Avoid low-yield lateral expansion across the same transform family. "
                        "Prefer deeper enrichment on strong pivots or finish when only exhausted paths remain."
                    ),
                }
            )

        messages.append(
            {
                "role": "system",
                "content": (
                    "When you run a transform, the transform_name must exactly match a name returned by "
                    "list_transforms for that specific entity. Do not invent or paraphrase transform names."
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

    @staticmethod
    def _render_project_memory(project_memory: object) -> str:
        summary = getattr(project_memory, "summary", "") or ""
        known_facts = getattr(project_memory, "known_facts", []) or []
        recent_findings = getattr(project_memory, "recent_findings", []) or []
        exhausted_paths = getattr(project_memory, "exhausted_paths", []) or []
        recent_runs = getattr(project_memory, "recent_runs", []) or []

        sections: list[str] = ["Project memory from prior AI Investigator activity:"]
        if summary:
            sections.append(f"Summary:\n{summary}")
        if known_facts:
            sections.append("Known facts:\n" + "\n".join(f"- {item}" for item in known_facts[-6:]))
        if recent_findings:
            sections.append("Recent findings:\n" + "\n".join(f"- {item}" for item in recent_findings[-6:]))
        if exhausted_paths:
            sections.append("Exhausted paths:\n" + "\n".join(f"- {item}" for item in exhausted_paths[-4:]))
        if recent_runs:
            rendered_runs = []
            for item in recent_runs[-4:]:
                prompt = getattr(item, "prompt", "")
                status = getattr(item, "status", "")
                run_summary = getattr(item, "summary", "")
                rendered_runs.append(f"- [{status}] {prompt}: {run_summary}")
            sections.append("Recent runs:\n" + "\n".join(rendered_runs))
        return "\n\n".join(sections)

    def _render_goal_focus(self, prompt: str) -> str:
        normalized = prompt.lower()
        targets = [keyword for keyword in self.PLATFORM_KEYWORDS if keyword in normalized]
        if not targets:
            return (
                "Stay tightly aligned to the user goal. Prefer direct enrichment of the requested target over "
                "broad lateral pivots. Finish once the goal is sufficiently answered and no clearly better direct "
                "transform remains."
            )

        rendered_targets = ", ".join(sorted(set(targets)))
        return (
            f"Goal focus: the user explicitly asked about {rendered_targets}. "
            "Prioritize entities and transforms directly related to that target. "
            "Do not pivot into unrelated sibling accounts unless they are clearly needed to answer the target question. "
            "Once you identify the target entity and complete one or two direct enrichments on it, prefer summarizing "
            "the findings instead of continuing broad exploration."
        )

    @staticmethod
    def _render_resume_context(run: AgentRun) -> str:
        if not isinstance(run.config, dict):
            return ""
        resume = run.config.get("resume_context")
        if not isinstance(resume, dict):
            return ""

        source_run_id = str(resume.get("source_run_id") or "").strip()
        source_status = str(resume.get("source_status") or "").strip()
        source_summary = str(resume.get("source_summary") or "").strip()
        source_error = str(resume.get("source_error") or "").strip()
        last_step_number = resume.get("last_completed_step_number")
        recent_steps = resume.get("recent_steps") if isinstance(resume.get("recent_steps"), list) else []
        attempted_actions = resume.get("attempted_actions") if isinstance(resume.get("attempted_actions"), list) else []

        lines = [
            "Resume context from a previous investigator run:",
            f"- source run id: {source_run_id or 'unknown'}",
            f"- source status: {source_status or 'unknown'}",
        ]
        if last_step_number is not None:
            lines.append(f"- last completed step number: {last_step_number}")
        if source_summary:
            lines.append(f"- prior summary: {source_summary}")
        if source_error:
            lines.append(f"- prior error: {source_error}")
        if recent_steps:
            lines.append("Recent steps before the prior run stopped:")
            lines.extend(f"- {str(item)}" for item in recent_steps[-6:])
        if attempted_actions:
            lines.append("Previously attempted actions to avoid repeating:")
            lines.extend(f"- {str(item)}" for item in attempted_actions[-10:])
        lines.append(
            "Continue from these collected results. Do not restart the investigation from scratch or repeat the same actions unless new evidence justifies it."
        )
        return "\n".join(lines)

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

    @staticmethod
    def _summarize_attempted_actions(steps: list[AgentStep]) -> str:
        summaries: list[str] = []
        seen: set[str] = set()
        tool_calls = [step for step in steps if step.type.value == "tool_call" and step.tool_name]
        for step in tool_calls[-12:]:
            params = step.tool_input or {}
            tool_name = step.tool_name or ""
            if tool_name == "run_transform":
                signature = (
                    f"{tool_name}:{params.get('transform_name')}:{params.get('entity_id') or params.get('entity_value')}"
                )
            else:
                signature = f"{tool_name}:{str(params)}"
            if signature in seen:
                continue
            seen.add(signature)
            summaries.append(f"- {tool_name} {str(params)[:200]}")
        return "\n".join(summaries)

    @staticmethod
    def _summarize_policy_feedback(run: AgentRun) -> str:
        feedback = run.config.get("policy_feedback") if isinstance(run.config, dict) else None
        if not feedback:
            return ""
        items = feedback if isinstance(feedback, list) else [str(feedback)]
        return "\n".join(f"- {str(item)[:300]}" for item in items[-3:])

    @staticmethod
    def _summarize_transform_progress(run: AgentRun) -> str:
        if not isinstance(run.config, dict):
            return ""

        memory_items = run.config.get("transform_memory") or []
        recent_memory = [
            item for item in memory_items[-6:]
            if isinstance(item, dict)
        ]
        exhausted = [
            str(item).strip()
            for item in (run.config.get("exhausted_transform_families") or [])
            if str(item).strip()
        ]

        lines: list[str] = []
        if recent_memory:
            for item in recent_memory:
                transform_name = str(item.get("transform_name") or "unknown")
                target = str(item.get("target") or "unknown")
                new_entities = int(item.get("new_entity_count") or 0)
                new_edges = int(item.get("new_edge_count") or 0)
                types = item.get("new_entity_types") or []
                type_text = ", ".join(str(entry) for entry in types[:4]) if isinstance(types, list) and types else "no new types"
                yield_tag = "low-yield" if item.get("low_yield") else "productive"
                lines.append(
                    f"- {transform_name} on {target}: {new_entities} new entities, {new_edges} new edges, {type_text} [{yield_tag}]"
                )
        if exhausted:
            lines.append(f"- exhausted transform families: {', '.join(exhausted)}")
        return "\n".join(lines)
