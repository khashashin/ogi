"""Plugin management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ogi.models import PluginInfo, UserProfile
from ogi.api.auth import get_current_user, require_admin_user
from ogi.api.dependencies import get_plugin_engine, get_transform_engine, get_user_plugin_preference_store
from ogi.store.user_plugin_preference_store import UserPluginPreferenceStore

router = APIRouter(prefix="/plugins", tags=["plugins"])


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
