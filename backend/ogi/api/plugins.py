"""Plugin management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ogi.models import PluginInfo, UserProfile
from ogi.api.auth import get_current_user
from ogi.api.dependencies import get_plugin_engine, get_transform_engine
from ogi.config import settings

router = APIRouter(prefix="/plugins", tags=["plugins"])


@router.get("", response_model=list[PluginInfo])
async def list_plugins(
    current_user: UserProfile = Depends(get_current_user),
) -> list[PluginInfo]:
    engine = get_plugin_engine()
    return engine.list_plugins()


@router.get("/{name}", response_model=PluginInfo)
async def get_plugin(
    name: str,
    current_user: UserProfile = Depends(get_current_user),
) -> PluginInfo:
    engine = get_plugin_engine()
    plugin = engine.get_plugin(name)
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return plugin


@router.post("/{name}/enable", response_model=PluginInfo)
async def toggle_plugin(
    name: str,
    current_user: UserProfile = Depends(get_current_user),
) -> PluginInfo:
    plugin_engine = get_plugin_engine()
    transform_engine = get_transform_engine()
    plugin = plugin_engine.get_plugin(name)
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    
    if plugin.enabled:
        plugin.enabled = False
        old_names = plugin_engine._plugin_transforms.get(name, [])
        for t_name in old_names:
            transform_engine._transforms.pop(t_name, None)
    else:
        plugin.enabled = True
        transforms = plugin_engine.load_transforms(name)
        new_names: list[str] = []
        for t in transforms:
            transform_engine.register(t)
            new_names.append(t.name)
        plugin.transform_count = len(transforms)
        plugin.transform_names = new_names
        plugin_engine._plugin_transforms[name] = new_names
        
    return plugin


@router.post("/{name}/reload", response_model=PluginInfo)
async def reload_plugin(
    name: str,
    current_user: UserProfile = Depends(get_current_user),
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
