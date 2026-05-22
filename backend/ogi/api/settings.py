from fastapi import APIRouter
from pydantic import BaseModel

from ogi.config import settings

router = APIRouter(prefix="/settings", tags=["settings"])


class CapabilitiesResponse(BaseModel):
    cloud_export_enabled: bool


@router.get("/capabilities", response_model=CapabilitiesResponse)
async def get_capabilities() -> CapabilitiesResponse:
    return CapabilitiesResponse(
        cloud_export_enabled=bool(settings.supabase_url and settings.supabase_service_role_key),
    )
