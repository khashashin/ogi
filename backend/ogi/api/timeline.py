from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from ogi.api.auth import require_project_viewer
from ogi.api.dependencies import get_timeline_store
from ogi.models import TimelineResponse
from ogi.store.timeline_store import TimelineStore

router = APIRouter(prefix="/projects/{project_id}", tags=["timeline"])


@router.get("/timeline", response_model=TimelineResponse)
async def get_timeline(
    project_id: UUID,
    interval: str = Query("day", pattern="^(minute|hour|day|week)$"),
    since: datetime | None = Query(None, description="Include events on/after this ISO timestamp"),
    until: datetime | None = Query(None, description="Include events on/before this ISO timestamp"),
    _role: str = Depends(require_project_viewer),
    store: TimelineStore = Depends(get_timeline_store),
) -> TimelineResponse:
    return await store.get_timeline(project_id, interval=interval, since=since, until=until)
