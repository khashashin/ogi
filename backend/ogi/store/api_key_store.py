"""Encrypted API key storage for per-user transform credentials."""
from __future__ import annotations

import base64
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from ogi.models.api_key import ApiKey


class ApiKeyStore:
    """CRUD for per-user API keys (service_name → encrypted_key)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def list_services(self, user_id: UUID) -> list[str]:
        """Return service names for which the user has stored keys."""
        stmt = select(ApiKey.service_name).where(ApiKey.user_id == user_id).order_by(ApiKey.service_name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_key(self, user_id: UUID, service_name: str) -> str | None:
        """Return decrypted key or None."""
        stmt = select(ApiKey.encrypted_key).where(
            ApiKey.user_id == user_id, 
            ApiKey.service_name == service_name
        )
        result = await self.session.execute(stmt)
        encrypted = result.scalar_one_or_none()
        
        if not encrypted:
            return None
        return self._decrypt(encrypted)

    async def set_key(self, user_id: UUID, service_name: str, key: str) -> None:
        """Store or update an API key."""
        stmt = select(ApiKey).where(
            ApiKey.user_id == user_id, 
            ApiKey.service_name == service_name
        )
        result = await self.session.execute(stmt)
        entry = result.scalar_one_or_none()
        
        encrypted = self._encrypt(key)
        
        if entry:
            entry.encrypted_key = encrypted
        else:
            entry = ApiKey(user_id=user_id, service_name=service_name, encrypted_key=encrypted)
            
        self.session.add(entry)
        await self.session.commit()

    async def delete_key(self, user_id: UUID, service_name: str) -> bool:
        """Remove an API key. Returns True if one was deleted."""
        stmt = select(ApiKey).where(
            ApiKey.user_id == user_id, 
            ApiKey.service_name == service_name
        )
        result = await self.session.execute(stmt)
        entry = result.scalar_one_or_none()
        
        if entry:
            await self.session.delete(entry)
            await self.session.commit()
            return True
        return False

    # ------------------------------------------------------------------
    # Encryption helpers (simple base64 encoding — swap for Fernet/etc.)
    # ------------------------------------------------------------------

    @staticmethod
    def _encrypt(plain: str) -> str:
        return base64.b64encode(plain.encode()).decode()

    @staticmethod
    def _decrypt(encrypted: str) -> str:
        return base64.b64decode(encrypted.encode()).decode()
