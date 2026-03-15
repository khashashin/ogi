from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ogi.agent.models import (
    AgentRun,
    AgentRunStatus,
    AgentStep,
    AgentStepStatus,
    BudgetConfig,
    ScopeConfig,
    StartAgentRunRequest,
    StepApprovalRequest,
    UsageInfo,
)
from ogi.agent.orchestrator import build_agent_event, publish_agent_event
from ogi.agent.store import AgentRunStore, AgentStepStore
from ogi.api.auth import get_current_user, require_project_editor, require_project_viewer
from ogi.api.dependencies import get_agent_run_store, get_agent_step_store, get_audit_log_store, get_redis
from ogi.config import settings
from ogi.models import AuditLogCreate, UserProfile
from ogi.store.audit_log_store import AuditLogStore

router = APIRouter(prefix="/projects/{project_id}/agent", tags=["agent"])


def _default_budget(payload: BudgetConfig | None) -> dict[str, int]:
    requested = payload or BudgetConfig()
    max_steps = requested.max_steps or settings.agent_default_max_steps
    max_transforms = requested.max_transforms or settings.agent_default_max_transforms
    max_runtime_sec = requested.max_runtime_sec or settings.agent_default_max_runtime_sec
    return {
        "max_steps": min(max_steps, settings.agent_max_max_steps),
        "max_transforms": min(max_transforms, settings.agent_max_max_transforms),
        "max_runtime_sec": min(max_runtime_sec, settings.agent_max_max_runtime_sec),
    }

async def _load_run_or_404(project_id: UUID, run_id: UUID, store: AgentRunStore) -> AgentRun:
    run = await store.get(run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return run


async def _load_step_or_404(run_id: UUID, step_id: UUID, store: AgentStepStore) -> AgentStep:
    step = await store.get(step_id)
    if step is None or step.run_id != run_id:
        raise HTTPException(status_code=404, detail="Agent step not found")
    return step


@router.post("/start", response_model=AgentRun, status_code=201)
async def start_agent_run(
    project_id: UUID,
    data: StartAgentRunRequest,
    current_user: UserProfile = Depends(get_current_user),
    _role: str = Depends(require_project_editor),
    run_store: AgentRunStore = Depends(get_agent_run_store),
    audit_store: AuditLogStore = Depends(get_audit_log_store),
) -> AgentRun:
    if not settings.agent_enabled:
        raise HTTPException(status_code=404, detail="AI Investigator is disabled")

    if not data.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt is required")
    if data.scope.mode == "selected" and len(data.scope.entity_ids) == 0:
        raise HTTPException(status_code=400, detail="Selected scope requires entity_ids")

    active = await run_store.get_active_for_project(project_id)
    if active is not None:
        raise HTTPException(status_code=409, detail="An active AI investigation already exists for this project")

    run = AgentRun(
        project_id=project_id,
        user_id=current_user.id,
        status=AgentRunStatus.PENDING,
        scope=ScopeConfig(mode=data.scope.mode, entity_ids=data.scope.entity_ids).model_dump(mode="json"),
        prompt=data.prompt.strip(),
        provider=settings.llm_provider,
        model=settings.llm_model,
        budget=_default_budget(data.budget),
        usage=UsageInfo().model_dump(mode="json"),
    )
    created = await run_store.create(run)
    await audit_store.create(
        project_id,
        current_user.id,
        AuditLogCreate(
            action="agent.run_started",
            resource_type="agent_run",
            resource_id=str(created.id),
            details={
                "prompt": created.prompt,
                "scope": created.scope,
                "budget": created.budget,
            },
        ),
    )
    publish_agent_event(
        get_redis(),
        build_agent_event(
            event_type="agent_run_started",
            run=created,
        ),
    )
    return created


@router.get("/runs", response_model=list[AgentRun])
async def list_agent_runs(
    project_id: UUID,
    statuses: str | None = Query(default=None, description="Comma-separated run statuses"),
    limit: int = Query(200, ge=1, le=1000),
    _role: str = Depends(require_project_viewer),
    run_store: AgentRunStore = Depends(get_agent_run_store),
) -> list[AgentRun]:
    parsed_statuses: list[AgentRunStatus] | None = None
    if statuses:
        parsed_statuses = []
        for item in statuses.split(","):
            raw = item.strip()
            if not raw:
                continue
            try:
                parsed_statuses.append(AgentRunStatus(raw))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=f"Invalid agent run status '{raw}'") from exc
    return await run_store.list_by_project(project_id, parsed_statuses, limit=limit)


@router.get("/runs/{run_id}", response_model=AgentRun)
async def get_agent_run(
    project_id: UUID,
    run_id: UUID,
    _role: str = Depends(require_project_viewer),
    run_store: AgentRunStore = Depends(get_agent_run_store),
) -> AgentRun:
    return await _load_run_or_404(project_id, run_id, run_store)


@router.get("/runs/{run_id}/steps", response_model=list[AgentStep])
async def list_agent_steps(
    project_id: UUID,
    run_id: UUID,
    _role: str = Depends(require_project_viewer),
    run_store: AgentRunStore = Depends(get_agent_run_store),
    step_store: AgentStepStore = Depends(get_agent_step_store),
) -> list[AgentStep]:
    await _load_run_or_404(project_id, run_id, run_store)
    return await step_store.list_for_run(run_id)


@router.post("/runs/{run_id}/cancel", response_model=AgentRun)
async def cancel_agent_run(
    project_id: UUID,
    run_id: UUID,
    current_user: UserProfile = Depends(get_current_user),
    _role: str = Depends(require_project_editor),
    run_store: AgentRunStore = Depends(get_agent_run_store),
    audit_store: AuditLogStore = Depends(get_audit_log_store),
) -> AgentRun:
    run = await _load_run_or_404(project_id, run_id, run_store)
    if run.status in (AgentRunStatus.COMPLETED, AgentRunStatus.FAILED, AgentRunStatus.CANCELLED):
        raise HTTPException(status_code=400, detail=f"Cannot cancel a {run.status.value} run")

    run.status = AgentRunStatus.CANCELLED
    run.completed_at = datetime.now(timezone.utc)
    updated = await run_store.save(run)
    await audit_store.create(
        project_id,
        current_user.id,
        AuditLogCreate(
            action="agent.run_cancelled",
            resource_type="agent_run",
            resource_id=str(updated.id),
            details={"run_id": str(updated.id)},
        ),
    )
    publish_agent_event(
        get_redis(),
        build_agent_event(
            event_type="agent_run_cancelled",
            run=updated,
        ),
    )
    return updated


@router.post("/runs/{run_id}/steps/{step_id}/approve", response_model=AgentStep)
async def approve_agent_step(
    project_id: UUID,
    run_id: UUID,
    step_id: UUID,
    _data: StepApprovalRequest,
    current_user: UserProfile = Depends(get_current_user),
    _role: str = Depends(require_project_editor),
    run_store: AgentRunStore = Depends(get_agent_run_store),
    step_store: AgentStepStore = Depends(get_agent_step_store),
    audit_store: AuditLogStore = Depends(get_audit_log_store),
) -> AgentStep:
    run = await _load_run_or_404(project_id, run_id, run_store)
    step = await _load_step_or_404(run.id, step_id, step_store)
    if step.status != AgentStepStatus.WAITING_APPROVAL:
        raise HTTPException(status_code=400, detail=f"Step is not waiting for approval: {step.status.value}")

    approval_payload = dict(step.approval_payload or {})
    approval_payload["decision"] = "approved"
    if _data.note:
        approval_payload["note"] = _data.note
    step.approval_payload = approval_payload
    step.status = AgentStepStatus.APPROVED
    step.completed_at = datetime.now(timezone.utc)
    updated = await step_store.save(step)
    if run.status == AgentRunStatus.PAUSED:
        run.status = AgentRunStatus.PENDING
        await run_store.save(run)
    await audit_store.create(
        project_id,
        current_user.id,
        AuditLogCreate(
            action="agent.approval_granted",
            resource_type="agent_step",
            resource_id=str(updated.id),
            details={"run_id": str(run.id), "step_id": str(updated.id)},
        ),
    )
    publish_agent_event(
        get_redis(),
        build_agent_event(
            event_type="agent_approval_resolved",
            run=run,
            step=updated,
        ),
    )
    return updated


@router.post("/runs/{run_id}/steps/{step_id}/reject", response_model=AgentStep)
async def reject_agent_step(
    project_id: UUID,
    run_id: UUID,
    step_id: UUID,
    _data: StepApprovalRequest,
    current_user: UserProfile = Depends(get_current_user),
    _role: str = Depends(require_project_editor),
    run_store: AgentRunStore = Depends(get_agent_run_store),
    step_store: AgentStepStore = Depends(get_agent_step_store),
    audit_store: AuditLogStore = Depends(get_audit_log_store),
) -> AgentStep:
    run = await _load_run_or_404(project_id, run_id, run_store)
    step = await _load_step_or_404(run.id, step_id, step_store)
    if step.status != AgentStepStatus.WAITING_APPROVAL:
        raise HTTPException(status_code=400, detail=f"Step is not waiting for approval: {step.status.value}")

    approval_payload = dict(step.approval_payload or {})
    approval_payload["decision"] = "rejected"
    if _data.note:
        approval_payload["note"] = _data.note
    step.approval_payload = approval_payload
    step.status = AgentStepStatus.REJECTED
    step.completed_at = datetime.now(timezone.utc)
    updated = await step_store.save(step)
    if run.status != AgentRunStatus.CANCELLED:
        run.status = AgentRunStatus.PAUSED
        await run_store.save(run)
    await audit_store.create(
        project_id,
        current_user.id,
        AuditLogCreate(
            action="agent.approval_rejected",
            resource_type="agent_step",
            resource_id=str(updated.id),
            details={"run_id": str(run.id), "step_id": str(updated.id)},
        ),
    )
    publish_agent_event(
        get_redis(),
        build_agent_event(
            event_type="agent_approval_resolved",
            run=run,
            step=updated,
        ),
    )
    return updated
