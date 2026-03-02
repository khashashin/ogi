"""Registry proxy API — lets the frontend browse, install, and manage transforms."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ogi.api.auth import get_current_user, require_admin_user
from ogi.api.dependencies import get_registry_client, get_transform_installer
from ogi.cli.registry import RegistryClient, RegistryTransform
from ogi.cli.installer import TransformInstaller, InstallError
from ogi.config import settings
from ogi.models import UserProfile

router = APIRouter(prefix="/registry", tags=["registry"])


class InstallResult(BaseModel):
    slug: str
    version: str
    files_installed: int
    message: str


class UpdateCheckItem(BaseModel):
    slug: str
    installed_version: str
    latest_version: str


# -------------------------------------------------------------------
# Browse / search
# -------------------------------------------------------------------


@router.get("/index")
async def get_index(
    current_user: UserProfile = Depends(get_current_user),
) -> dict[str, object]:
    """Return the full cached registry index."""
    registry = get_registry_client()
    index = await registry.fetch_index()
    can_manage = (
        (not settings.supabase_url or not settings.supabase_anon_key)
        or current_user.email.lower() in settings.admin_emails
    )
    payload = dict(index)
    payload["can_manage"] = can_manage
    return payload


@router.get("/search")
async def search_transforms(
    q: str = Query("", description="Search query"),
    category: str | None = Query(None, description="Filter by category"),
    tier: str | None = Query(None, description="Filter by verification tier"),
    current_user: UserProfile = Depends(get_current_user),
) -> list[RegistryTransform]:
    """Search transforms in the registry."""
    registry = get_registry_client()
    await registry.fetch_index()
    return registry.search(q, category=category, tier=tier)


# -------------------------------------------------------------------
# Install / update / remove
# -------------------------------------------------------------------


@router.post("/install/{slug}", response_model=InstallResult)
async def install_transform(
    slug: str,
    current_user: UserProfile = Depends(get_current_user),
    admin_user: UserProfile = Depends(require_admin_user),
) -> InstallResult:
    """Download and install a transform from the registry."""
    registry = get_registry_client()
    await registry.fetch_index()

    # Cloud tier enforcement
    if settings.deployment_mode == "cloud":
        meta = registry.get_transform(slug)
        if meta is None:
            raise HTTPException(404, f"Transform '{slug}' not found")
        tier = meta.get("verification_tier", "community")
        if tier not in settings.sandbox_allowed_tiers:
            raise HTTPException(
                403,
                f"'{slug}' is tier '{tier}'. "
                f"Cloud mode allows: {settings.sandbox_allowed_tiers}",
            )

    installer = get_transform_installer()
    try:
        files = await installer.install(slug)
    except InstallError as exc:
        raise HTTPException(400, str(exc))

    meta = registry.get_transform(slug)
    version = meta.get("version", "") if meta else ""

    return InstallResult(
        slug=slug,
        version=version,
        files_installed=len(files),
        message=f"'{slug}' v{version} installed successfully",
    )


@router.delete("/remove/{slug}")
async def remove_transform(
    slug: str,
    current_user: UserProfile = Depends(get_current_user),
    admin_user: UserProfile = Depends(require_admin_user),
) -> dict[str, str]:
    """Uninstall a transform."""
    installer = get_transform_installer()
    try:
        installer.remove(slug)
    except InstallError as exc:
        raise HTTPException(400, str(exc))
    return {"status": "removed", "slug": slug}


@router.post("/update/{slug}", response_model=InstallResult)
async def update_transform(
    slug: str,
    current_user: UserProfile = Depends(get_current_user),
    admin_user: UserProfile = Depends(require_admin_user),
) -> InstallResult:
    """Update a single transform to the latest version."""
    registry = get_registry_client()
    await registry.fetch_index()
    installer = get_transform_installer()

    try:
        updated = await installer.update(slug)
    except InstallError as exc:
        raise HTTPException(400, str(exc))

    if not updated:
        meta = registry.get_transform(slug)
        version = meta.get("version", "") if meta else ""
        return InstallResult(
            slug=slug,
            version=version,
            files_installed=0,
            message=f"'{slug}' is already up to date",
        )

    meta = registry.get_transform(slug)
    version = meta.get("version", "") if meta else ""
    return InstallResult(
        slug=slug,
        version=version,
        files_installed=0,
        message=f"'{slug}' updated to v{version}",
    )


@router.get("/check-updates", response_model=list[UpdateCheckItem])
async def check_updates(
    current_user: UserProfile = Depends(get_current_user),
) -> list[UpdateCheckItem]:
    """List transforms that have updates available."""
    registry = get_registry_client()
    await registry.fetch_index()
    installer = get_transform_installer()

    updates = await installer.check_updates()
    return [
        UpdateCheckItem(slug=s, installed_version=old, latest_version=new)
        for s, old, new in updates
    ]
