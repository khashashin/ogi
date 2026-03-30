from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ogi.api.auth import require_admin_user
from ogi.config import settings
from ogi.db.database import get_session
from ogi.models import (
    TelemetryIngestPayload,
    TelemetryInstanceSummary,
    TelemetryOverviewResponse,
    UserProfile,
)
from ogi.telemetry import telemetry_manager

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


def _require_cloud_mode() -> None:
    if settings.deployment_mode != "cloud":
        raise HTTPException(status_code=404, detail="Telemetry endpoint not available")


def _derive_country_code(request: Request) -> str | None:
    for header in ("CF-IPCountry", "X-Vercel-IP-Country"):
        value = request.headers.get(header)
        if value:
            normalized = value.strip().upper()
            if normalized and normalized != "XX":
                return normalized[:8]
    return None


@router.post("/ingest", status_code=202)
async def ingest_telemetry(
    payload: TelemetryIngestPayload,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    _require_cloud_mode()
    country_code = _derive_country_code(request)
    await telemetry_manager.store_ingest_payload(session, payload, country_code=country_code)
    return {"status": "accepted"}


@router.get("/admin/overview", response_model=TelemetryOverviewResponse)
async def telemetry_admin_overview(
    _admin: UserProfile = Depends(require_admin_user),
    session: AsyncSession = Depends(get_session),
) -> TelemetryOverviewResponse:
    _require_cloud_mode()
    return await telemetry_manager.admin_overview(session)


@router.get("/admin/instances", response_model=list[TelemetryInstanceSummary])
async def telemetry_admin_instances(
    limit: int = 50,
    _admin: UserProfile = Depends(require_admin_user),
    session: AsyncSession = Depends(get_session),
) -> list[TelemetryInstanceSummary]:
    _require_cloud_mode()
    safe_limit = max(1, min(limit, 200))
    return await telemetry_manager.list_instances(session, limit=safe_limit)
