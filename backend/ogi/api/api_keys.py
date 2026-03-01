"""API key management endpoints.

Users can store per-service API keys (e.g. VirusTotal, Shodan) that are
automatically injected into transform configs at runtime.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ogi.models import UserProfile
from ogi.api.auth import get_current_user
from ogi.api.dependencies import get_api_key_store
from ogi.store.api_key_store import ApiKeyStore

router = APIRouter(prefix="/settings/api-keys", tags=["api-keys"])


class ApiKeyCreate(BaseModel):
    service_name: str
    key: str


class ApiKeyEntry(BaseModel):
    service_name: str


@router.get("", response_model=list[ApiKeyEntry])
async def list_api_keys(
    current_user: UserProfile = Depends(get_current_user),
    store: ApiKeyStore = Depends(get_api_key_store),
) -> list[ApiKeyEntry]:
    services = await store.list_services(current_user.id)
    return [ApiKeyEntry(service_name=s) for s in services]


@router.post("", status_code=201)
async def save_api_key(
    data: ApiKeyCreate,
    current_user: UserProfile = Depends(get_current_user),
    store: ApiKeyStore = Depends(get_api_key_store),
) -> ApiKeyEntry:
    await store.set_key(current_user.id, data.service_name, data.key)
    return ApiKeyEntry(service_name=data.service_name)


@router.delete("/{service_name}", status_code=204)
async def delete_api_key(
    service_name: str,
    current_user: UserProfile = Depends(get_current_user),
    store: ApiKeyStore = Depends(get_api_key_store),
) -> None:
    deleted = await store.delete_key(current_user.id, service_name)
    if not deleted:
        raise HTTPException(status_code=404, detail="API key not found")
