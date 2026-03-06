from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from ogi.api.auth import get_current_user, require_project_editor, require_project_viewer
from ogi.api.dependencies import get_audit_log_store, get_project_event_store
from ogi.models import (
    AuditLog,
    AuditLogCreate,
    LocationAggregate,
    ProjectEventsResponse,
    TemporalGeoConventions,
    UserProfile,
)
from ogi.store.audit_log_store import AuditLogStore
from ogi.store.project_event_store import ProjectEventStore

router = APIRouter(prefix="/projects/{project_id}", tags=["events"])


@router.get("/events", response_model=ProjectEventsResponse)
async def list_project_events(
    project_id: UUID,
    since: datetime | None = Query(None, description="Include events on/after this ISO timestamp"),
    until: datetime | None = Query(None, description="Include events on/before this ISO timestamp"),
    limit: int = Query(200, ge=1, le=1000),
    _role: str = Depends(require_project_viewer),
    store: ProjectEventStore = Depends(get_project_event_store),
) -> ProjectEventsResponse:
    items = await store.list_events(project_id, since=since, until=until, limit=limit)
    return ProjectEventsResponse(conventions=TemporalGeoConventions(), items=items)


@router.get("/locations", response_model=list[LocationAggregate])
async def list_project_locations(
    project_id: UUID,
    limit: int = Query(200, ge=1, le=1000),
    _role: str = Depends(require_project_viewer),
    store: ProjectEventStore = Depends(get_project_event_store),
) -> list[LocationAggregate]:
    return await store.list_locations(project_id, limit=limit)


@router.post("/audit-logs", response_model=AuditLog, status_code=201)
async def create_audit_log(
    project_id: UUID,
    data: AuditLogCreate,
    current_user: UserProfile = Depends(get_current_user),
    _role: str = Depends(require_project_editor),
    store: AuditLogStore = Depends(get_audit_log_store),
) -> AuditLog:
    return await store.create(project_id, current_user.id, data)


@router.get("/audit-logs", response_model=list[AuditLog])
async def list_audit_logs(
    project_id: UUID,
    limit: int = Query(200, ge=1, le=1000),
    _role: str = Depends(require_project_viewer),
    store: AuditLogStore = Depends(get_audit_log_store),
) -> list[AuditLog]:
    return await store.list_by_project(project_id, limit=limit)
