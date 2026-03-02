import base64
from uuid import uuid4

import pytest
from fastapi import HTTPException

from ogi.api.auth import require_admin_user
from ogi.config import settings
from ogi.models import UserProfile
from ogi.store.api_key_store import ApiKeyStore


@pytest.mark.asyncio
async def test_require_admin_user_blocks_non_admin(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "supabase_url", "https://example.supabase.co")
    monkeypatch.setattr(settings, "supabase_anon_key", "anon-key")
    monkeypatch.setattr(settings, "admin_emails", "admin@example.com")

    user = UserProfile(id=uuid4(), email="user@example.com")
    with pytest.raises(HTTPException) as exc:
        await require_admin_user(user)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_admin_user_allows_local_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "supabase_url", "")
    monkeypatch.setattr(settings, "supabase_anon_key", "")
    monkeypatch.setattr(settings, "admin_emails", "")

    user = UserProfile(id=uuid4(), email="local@example.com")
    resolved = await require_admin_user(user)
    assert resolved.id == user.id


def test_api_key_store_encrypts_and_decrypts_v1(monkeypatch: pytest.MonkeyPatch):
    key = "k0f97udxEhQ4duzTQESsQNmjUG74U7SMiFd7LrD0WBE="
    monkeypatch.setattr(settings, "api_key_encryption_key", key)

    store = ApiKeyStore(session=None)  # type: ignore[arg-type]
    encrypted = store._encrypt("secret-value")
    assert encrypted.startswith("v1:")
    assert encrypted != "secret-value"
    assert store._decrypt(encrypted) == "secret-value"


def test_api_key_store_reads_legacy_base64(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "api_key_encryption_key", None)

    store = ApiKeyStore(session=None)  # type: ignore[arg-type]
    legacy = base64.b64encode(b"legacy-secret").decode()
    assert store._decrypt(legacy) == "legacy-secret"
