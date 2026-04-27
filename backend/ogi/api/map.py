from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from ogi.api.auth import require_project_viewer
from ogi.api.dependencies import get_map_store
from ogi.models import MapPointsResponse, MapRoutesResponse
from ogi.store.map_store import MapStore

router = APIRouter(prefix="/projects/{project_id}/map", tags=["map"])


@router.get("/points", response_model=MapPointsResponse)
async def get_map_points(
    project_id: UUID,
    cluster: bool = Query(True),
    zoom: int = Query(3, ge=1, le=20),
    geocode_missing: bool = Query(True),
    _role: str = Depends(require_project_viewer),
    store: MapStore = Depends(get_map_store),
) -> MapPointsResponse:
    return await store.get_points(
        project_id,
        cluster=cluster,
        zoom=zoom,
        geocode_missing=geocode_missing,
    )


@router.get("/routes", response_model=MapRoutesResponse)
async def get_map_routes(
    project_id: UUID,
    geocode_missing: bool = Query(True),
    _role: str = Depends(require_project_viewer),
    store: MapStore = Depends(get_map_store),
) -> MapRoutesResponse:
    return await store.get_routes(project_id, geocode_missing=geocode_missing)
