from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from ogi.agent.models import AgentProjectMemory, AgentProjectMemoryRead, AgentProjectMemoryRunRecord, AgentRun, AgentStep, AgentStepType


class AgentProjectMemoryStore:
    MAX_KNOWN_FACTS = 20
    MAX_RECENT_FINDINGS = 12
    MAX_EXHAUSTED_PATHS = 12
    MAX_RECENT_RUNS = 8

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_for_project(self, project_id: UUID) -> AgentProjectMemory | None:
        stmt = select(AgentProjectMemory).where(AgentProjectMemory.project_id == project_id).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create_for_project(self, project_id: UUID) -> AgentProjectMemory:
        existing = await self.get_for_project(project_id)
        if existing is not None:
            return existing
        now = datetime.now(timezone.utc)
        memory = AgentProjectMemory(
            project_id=project_id,
            summary="",
            known_facts=[],
            recent_findings=[],
            exhausted_paths=[],
            recent_runs=[],
            created_at=now,
            updated_at=now,
        )
        self.session.add(memory)
        await self.session.commit()
        await self.session.refresh(memory)
        return memory

    async def save(self, memory: AgentProjectMemory) -> AgentProjectMemory:
        existing = await self.get_for_project(memory.project_id)
        if existing is not None:
            existing.summary = memory.summary
            existing.known_facts = list(memory.known_facts or [])
            existing.recent_findings = list(memory.recent_findings or [])
            existing.exhausted_paths = list(memory.exhausted_paths or [])
            existing.recent_runs = list(memory.recent_runs or [])
            existing.updated_at = datetime.now(timezone.utc)
            self.session.add(existing)
            await self.session.commit()
            await self.session.refresh(existing)
            return existing

        memory.updated_at = datetime.now(timezone.utc)
        self.session.add(memory)
        await self.session.commit()
        await self.session.refresh(memory)
        return memory

    async def reset_for_project(self, project_id: UUID) -> None:
        memory = await self.get_for_project(project_id)
        if memory is None:
            return
        await self.session.delete(memory)
        await self.session.commit()

    async def build_read_model(self, project_id: UUID) -> AgentProjectMemoryRead:
        memory = await self.get_for_project(project_id)
        if memory is None:
            now = datetime.now(timezone.utc)
            return AgentProjectMemoryRead(
                project_id=project_id,
                summary="",
                known_facts=[],
                recent_findings=[],
                exhausted_paths=[],
                recent_runs=[],
                updated_at=now,
            )
        return AgentProjectMemoryRead(
            project_id=memory.project_id,
            summary=memory.summary,
            known_facts=list(memory.known_facts or []),
            recent_findings=list(memory.recent_findings or []),
            exhausted_paths=list(memory.exhausted_paths or []),
            recent_runs=[
                AgentProjectMemoryRunRecord.model_validate(item)
                for item in (memory.recent_runs or [])
                if isinstance(item, dict)
            ],
            updated_at=memory.updated_at,
        )

    async def update_from_run(self, run: AgentRun, steps: list[AgentStep]) -> AgentProjectMemory:
        memory = await self.get_or_create_for_project(run.project_id)

        recent_findings = self._merge_unique(
            memory.recent_findings or [],
            self._extract_recent_findings(steps),
            self.MAX_RECENT_FINDINGS,
        )
        known_facts = self._merge_unique(
            memory.known_facts or [],
            self._extract_known_facts(run, steps),
            self.MAX_KNOWN_FACTS,
        )
        exhausted_paths = self._merge_unique(
            memory.exhausted_paths or [],
            self._extract_exhausted_paths(run),
            self.MAX_EXHAUSTED_PATHS,
        )
        recent_runs = self._merge_recent_runs(memory.recent_runs or [], run)

        memory.recent_findings = recent_findings
        memory.known_facts = known_facts
        memory.exhausted_paths = exhausted_paths
        memory.recent_runs = recent_runs
        memory.summary = self._build_summary(run, known_facts, recent_findings, exhausted_paths, recent_runs)
        memory.updated_at = datetime.now(timezone.utc)
        self.session.add(memory)
        await self.session.commit()
        await self.session.refresh(memory)
        return memory

    @staticmethod
    def _normalize_line(value: str) -> str:
        return " ".join(value.strip().split())

    def _merge_unique(self, existing: list[str], new_items: list[str], limit: int) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for item in [*existing, *new_items]:
            normalized = self._normalize_line(str(item))
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(normalized)
        return merged[-limit:]

    def _merge_recent_runs(self, existing: list[dict[str, Any]], run: AgentRun) -> list[dict[str, Any]]:
        entry = {
            "run_id": str(run.id),
            "prompt": run.prompt,
            "status": run.status.value if hasattr(run.status, "value") else str(run.status),
            "summary": run.summary or run.error or "Run in progress",
            "updated_at": run.updated_at.isoformat(),
        }
        merged = [
            item for item in existing
            if isinstance(item, dict) and str(item.get("run_id") or "") != str(run.id)
        ]
        merged.append(entry)
        return merged[-self.MAX_RECENT_RUNS:]

    def _extract_recent_findings(self, steps: list[AgentStep]) -> list[str]:
        findings: list[str] = []
        for step in steps:
            if step.type != AgentStepType.TOOL_RESULT:
                continue
            tool_output = step.tool_output or {}
            summary = self._normalize_line(str(tool_output.get("summary") or ""))
            if not summary:
                continue
            tool_name = step.tool_name or "tool"
            findings.append(f"{tool_name}: {summary}")
        return findings[-self.MAX_RECENT_FINDINGS:]

    def _extract_known_facts(self, run: AgentRun, steps: list[AgentStep]) -> list[str]:
        facts: list[str] = []
        if run.summary:
            facts.append(f"Run '{run.prompt}' concluded: {run.summary}")

        transform_memory = (run.config or {}).get("transform_memory") or []
        for item in transform_memory[-6:]:
            if not isinstance(item, dict):
                continue
            transform_name = self._normalize_line(str(item.get("transform_name") or ""))
            target = self._normalize_line(str(item.get("target") or ""))
            if not transform_name or not target:
                continue
            facts.append(
                f"{transform_name} on {target}: {int(item.get('new_entity_count') or 0)} new entities, "
                f"{int(item.get('new_edge_count') or 0)} new edges"
            )

        for step in steps[-8:]:
            if step.type != AgentStepType.TOOL_RESULT:
                continue
            tool_output = step.tool_output or {}
            summary = self._normalize_line(str(tool_output.get("summary") or ""))
            if not summary:
                continue
            if step.tool_name in {"run_transform", "create_entity", "finish_investigation"}:
                facts.append(summary)
        return facts[-self.MAX_KNOWN_FACTS:]

    def _extract_exhausted_paths(self, run: AgentRun) -> list[str]:
        exhausted_paths: list[str] = []
        for item in (run.config or {}).get("exhausted_transform_families", []) or []:
            normalized = self._normalize_line(str(item))
            if normalized:
                exhausted_paths.append(f"Transform family exhausted: {normalized}")
        for item in (run.config or {}).get("policy_feedback", []) or []:
            normalized = self._normalize_line(str(item))
            if normalized and ("low-yield" in normalized or "already executed" in normalized):
                exhausted_paths.append(normalized)
        return exhausted_paths[-self.MAX_EXHAUSTED_PATHS:]

    def _build_summary(
        self,
        run: AgentRun,
        known_facts: list[str],
        recent_findings: list[str],
        exhausted_paths: list[str],
        recent_runs: list[dict[str, Any]],
    ) -> str:
        parts = [f"Project memory tracks {len(recent_runs)} recent AI Investigator runs."]
        if run.summary:
            parts.append(f"Latest completed run: {self._normalize_line(run.summary)[:240]}")
        elif run.error:
            parts.append(f"Latest run error: {self._normalize_line(run.error)[:200]}")
        if known_facts:
            parts.append(f"Known facts: {' | '.join(known_facts[-3:])[:500]}")
        elif recent_findings:
            parts.append(f"Recent findings: {' | '.join(recent_findings[-3:])[:500]}")
        if exhausted_paths:
            parts.append(f"Exhausted paths: {' | '.join(exhausted_paths[-2:])[:300]}")
        return " ".join(parts)
