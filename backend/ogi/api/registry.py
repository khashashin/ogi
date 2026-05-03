"""Registry proxy API — lets the frontend browse, install, and manage transforms."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ogi.api.auth import get_current_user, require_admin_user
from ogi.api.dependencies import (
    get_plugin_engine,
    get_registry_client,
    get_system_audit_log_store,
    get_transform_engine,
    get_transform_installer,
)
from ogi.cli.registry import RegistryClient, RegistryTransform
from ogi.cli.installer import TransformInstaller, InstallError
from ogi.config import settings
from ogi.models import SystemAuditLogCreate, UserProfile
from ogi.store.system_audit_log_store import SystemAuditLogStore

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


def _reload_plugin_runtime(name: str) -> int:
    """Best-effort in-process plugin load so UI reflects install immediately."""
    plugin_engine = get_plugin_engine()
    transform_engine = get_transform_engine()

    # Refresh plugin manifest metadata from disk so version/description/input types
    # reflect the latest installed files after install or update.
    plugin = None
    for discovered in plugin_engine.discover():
        if discovered.name == name:
            plugin_engine.plugins[name] = discovered
            plugin = discovered
            break

    # Remove previously loaded transforms from this plugin.
    old_names = plugin_engine._plugin_transforms.get(name, [])
    for transform_name in old_names:
        transform_engine._transforms.pop(transform_name, None)

    # Load and register current transforms from disk.
    transforms = plugin_engine.load_transforms(name)
    new_names: list[str] = []
    for transform in transforms:
        transform_engine.register(transform)
        new_names.append(transform.name)
    plugin_engine._plugin_transforms[name] = new_names

    if plugin is not None:
        plugin.transform_count = len(transforms)
        plugin.transform_names = new_names

    return len(transforms)


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
    index = await registry.apply_dynamic_popularity(index)
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
    index = await registry.fetch_index()
    index = await registry.apply_dynamic_popularity(index)
    return registry.search_in_index(index, q, category=category, tier=tier)


@router.get("/popularity")
async def get_popularity(
    force: bool = Query(False, description="Force refresh of dynamic popularity cache"),
    current_user: UserProfile = Depends(get_current_user),
) -> dict[str, dict[str, object]]:
    """Return dynamic per-transform popularity map keyed by transform slug."""
    registry = get_registry_client()
    index = await registry.fetch_index()
    transforms = index.get("transforms", [])
    slugs = {t.get("slug", "") for t in transforms if t.get("slug")}
    popularity = await registry.get_dynamic_popularity(slugs, force=force)
    return {slug: dict(values) for slug, values in popularity.items()}


# -------------------------------------------------------------------
# Install / update / remove
# -------------------------------------------------------------------


@router.post("/install/{slug}", response_model=InstallResult)
async def install_transform(
    slug: str,
    current_user: UserProfile = Depends(get_current_user),
    admin_user: UserProfile = Depends(require_admin_user),
    audit_store: SystemAuditLogStore = Depends(get_system_audit_log_store),
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
    await audit_store.create(
        current_user.id,
        SystemAuditLogCreate(
            action="plugin.install",
            resource_type="plugin",
            resource_id=slug,
            details={
                "plugin_name": slug,
                "version": version,
                "verification_tier": meta.get("verification_tier", "community") if meta else "community",
                "api_key_services": [entry.get("service", "") for entry in meta.get("api_keys_required", [])] if meta else [],
            },
        ),
    )
    loaded_count = 0
    load_warning = ""
    try:
        loaded_count = _reload_plugin_runtime(slug)
    except Exception:
        load_warning = " Installed on disk; restart backend if it does not appear immediately."

    return InstallResult(
        slug=slug,
        version=version,
        files_installed=len(files),
        message=(
            f"'{slug}' v{version} installed successfully"
            f"{' and loaded' if loaded_count > 0 else ''}."
            f"{load_warning}"
        ),
    )


@router.delete("/remove/{slug}")
async def remove_transform(
    slug: str,
    current_user: UserProfile = Depends(get_current_user),
    admin_user: UserProfile = Depends(require_admin_user),
    audit_store: SystemAuditLogStore = Depends(get_system_audit_log_store),
) -> dict[str, str]:
    """Uninstall a transform."""
    installer = get_transform_installer()
    try:
        installer.remove(slug)
    except InstallError as exc:
        raise HTTPException(400, str(exc))
    await audit_store.create(
        current_user.id,
        SystemAuditLogCreate(
            action="plugin.remove",
            resource_type="plugin",
            resource_id=slug,
            details={"plugin_name": slug},
        ),
    )
    return {"status": "removed", "slug": slug}


@router.post("/update/{slug}", response_model=InstallResult)
async def update_transform(
    slug: str,
    current_user: UserProfile = Depends(get_current_user),
    admin_user: UserProfile = Depends(require_admin_user),
    audit_store: SystemAuditLogStore = Depends(get_system_audit_log_store),
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
    await audit_store.create(
        current_user.id,
        SystemAuditLogCreate(
            action="plugin.update",
            resource_type="plugin",
            resource_id=slug,
            details={
                "plugin_name": slug,
                "version": version,
                "verification_tier": meta.get("verification_tier", "community") if meta else "community",
                "api_key_services": [entry.get("service", "") for entry in meta.get("api_keys_required", [])] if meta else [],
            },
        ),
    )
    loaded_count = 0
    load_warning = ""
    try:
        loaded_count = _reload_plugin_runtime(slug)
    except Exception:
        load_warning = " Updated on disk; restart backend if it does not appear immediately."
    return InstallResult(
        slug=slug,
        version=version,
        files_installed=0,
        message=(
            f"'{slug}' updated to v{version}"
            f"{' and reloaded' if loaded_count > 0 else ''}."
            f"{load_warning}"
        ),
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
