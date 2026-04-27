from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ogi.api.auth import get_optional_user
from ogi.config import settings
from ogi.models import UserProfile
from ogi.telemetry import telemetry_docs_url

router = APIRouter(prefix="/settings", tags=["settings"])


class CapabilitiesResponse(BaseModel):
    cloud_export_enabled: bool
    deployment_mode: str
    cloud_billing_enabled: bool
    stripe_checkout_enabled: bool
    telemetry_enabled: bool
    telemetry_level: str
    telemetry_admin_enabled: bool
    telemetry_docs_url: str


@router.get("/capabilities", response_model=CapabilitiesResponse)
async def get_capabilities(
    current_user: UserProfile | None = Depends(get_optional_user),
) -> CapabilitiesResponse:
    telemetry_admin_enabled = (
        settings.deployment_mode == "cloud"
        and current_user is not None
        and current_user.email.lower() in settings.get_admin_emails()
    )
    return CapabilitiesResponse(
        cloud_export_enabled=bool(settings.supabase_url and settings.supabase_service_role_key),
        deployment_mode=settings.deployment_mode,
        cloud_billing_enabled=settings.effective_cloud_billing_enabled,
        stripe_checkout_enabled=settings.stripe_checkout_enabled,
        telemetry_enabled=settings.effective_telemetry_enabled,
        telemetry_level=settings.normalized_telemetry_level,
        telemetry_admin_enabled=telemetry_admin_enabled,
        telemetry_docs_url=telemetry_docs_url(),
    )
