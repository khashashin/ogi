"""Plugin management endpoints."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ogi.models import PluginInfo, UserProfile
from ogi.api.auth import get_current_user, require_admin_user
from ogi.api.dependencies import (
    get_audit_log_store,
    get_plugin_engine,
    get_transform_engine,
    get_user_plugin_preference_store,
)
from ogi.store.audit_log_store import AuditLogStore
from ogi.store.user_plugin_preference_store import UserPluginPreferenceStore

router = APIRouter(prefix="/plugins", tags=["plugins"])


class PluginApiKeyUsageEntry(BaseModel):
    service_name: str
    last_used_at: datetime | None = None


class PluginApiKeyUsageReportItem(BaseModel):
    plugin_name: str
    display_name: str
    verification_tier: str
    permissions: dict[str, bool]
    requested_services: list[str]
    usage: list[PluginApiKeyUsageEntry]


@router.get("", response_model=list[PluginInfo])
async def list_plugins(
    current_user: UserProfile = Depends(get_current_user),
    preferences: UserPluginPreferenceStore = Depends(get_user_plugin_preference_store),
) -> list[PluginInfo]:
    engine = get_plugin_engine()
    plugin_list = engine.list_plugins()
    preference_map = await preferences.list_for_user(current_user.id)
    return [
        plugin.model_copy(update={"enabled": preference_map.get(plugin.name, True)})
        for plugin in plugin_list
    ]


@router.get("/api-key-usage-report", response_model=list[PluginApiKeyUsageReportItem])
async def get_plugin_api_key_usage_report(
    _current_user: UserProfile = Depends(require_admin_user),
    store: AuditLogStore = Depends(get_audit_log_store),
) -> list[PluginApiKeyUsageReportItem]:
    plugin_engine = get_plugin_engine()
    plugin_list = plugin_engine.list_plugins()
    usage_logs = await store.list_by_action("transform.api_key_injected")

    latest_by_pair: dict[tuple[str, str], datetime] = {}
    for row in usage_logs:
        plugin_name = str(row.details.get("plugin_name") or "").strip()
        service_name = str(row.details.get("service_name") or "").strip()
        if not plugin_name or not service_name:
            continue
        key = (plugin_name, service_name)
        current = latest_by_pair.get(key)
        if current is None or row.created_at > current:
            latest_by_pair[key] = row.created_at

    report: list[PluginApiKeyUsageReportItem] = []
    for plugin in plugin_list:
        requested_services = sorted(
            {
                str(entry.get("service", "")).strip()
                for entry in (plugin.api_keys_required or [])
                if str(entry.get("service", "")).strip()
            }
        )
        usage = [
            PluginApiKeyUsageEntry(
                service_name=service_name,
                last_used_at=latest_by_pair.get((plugin.name, service_name)),
            )
            for service_name in requested_services
        ]
        report.append(
            PluginApiKeyUsageReportItem(
                plugin_name=plugin.name,
                display_name=plugin.display_name or plugin.name,
                verification_tier=plugin.verification_tier or "community",
                permissions=plugin.permissions or {},
                requested_services=requested_services,
                usage=usage,
            )
        )

    report.sort(key=lambda item: item.display_name.lower())
    return report


@router.get("/{name}", response_model=PluginInfo)
async def get_plugin(
    name: str,
    current_user: UserProfile = Depends(get_current_user),
    preferences: UserPluginPreferenceStore = Depends(get_user_plugin_preference_store),
) -> PluginInfo:
    engine = get_plugin_engine()
    plugin = engine.get_plugin(name)
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    enabled = await preferences.is_enabled(current_user.id, name, default=True)
    return plugin.model_copy(update={"enabled": enabled})


@router.post("/{name}/enable", response_model=PluginInfo)
async def enable_plugin(
    name: str,
    current_user: UserProfile = Depends(get_current_user),
    preferences: UserPluginPreferenceStore = Depends(get_user_plugin_preference_store),
) -> PluginInfo:
    plugin_engine = get_plugin_engine()
    plugin = plugin_engine.get_plugin(name)
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    await preferences.set_enabled(current_user.id, name, True)
    return plugin.model_copy(update={"enabled": True})


@router.post("/{name}/disable", response_model=PluginInfo)
async def disable_plugin(
    name: str,
    current_user: UserProfile = Depends(get_current_user),
    preferences: UserPluginPreferenceStore = Depends(get_user_plugin_preference_store),
) -> PluginInfo:
    plugin_engine = get_plugin_engine()
    plugin = plugin_engine.get_plugin(name)
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    await preferences.set_enabled(current_user.id, name, False)
    return plugin.model_copy(update={"enabled": False})


@router.post("/{name}/reload", response_model=PluginInfo)
async def reload_plugin(
    name: str,
    current_user: UserProfile = Depends(get_current_user),
    admin_user: UserProfile = Depends(require_admin_user),
) -> PluginInfo:
    """Reload transforms from a plugin's directory."""
    plugin_engine = get_plugin_engine()
    transform_engine = get_transform_engine()

    # Remove old transforms from this plugin
    old_names = plugin_engine._plugin_transforms.get(name, [])
    for t_name in old_names:
        transform_engine._transforms.pop(t_name, None)

    # Re-load
    transforms = plugin_engine.load_transforms(name)
    new_names: list[str] = []
    for t in transforms:
        transform_engine.register(t)
        new_names.append(t.name)

    plugin = plugin_engine.get_plugin(name)
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")

    plugin.transform_count = len(transforms)
    plugin.transform_names = new_names
    plugin_engine._plugin_transforms[name] = new_names
    return plugin

