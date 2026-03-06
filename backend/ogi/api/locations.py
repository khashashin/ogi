from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from ogi.api.auth import require_project_viewer
from ogi.api.dependencies import get_location_search_store
from ogi.models import LocationSuggestResponse
from ogi.store.location_search_store import LocationSearchStore

router = APIRouter(prefix="/projects/{project_id}/locations", tags=["locations"])


@router.get("/suggest", response_model=LocationSuggestResponse)
async def suggest_locations(
    project_id: UUID,
    q: str = Query("", min_length=0, max_length=200),
    limit: int = Query(5, ge=1, le=10),
    _role: str = Depends(require_project_viewer),
    store: LocationSearchStore = Depends(get_location_search_store),
) -> LocationSuggestResponse:
    return await store.suggest(q, limit=limit)
