from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from ogi.agent.settings_models import AgentUserSettings


class AgentSettingsStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_for_user(self, user_id: UUID) -> AgentUserSettings | None:
        stmt = select(AgentUserSettings).where(AgentUserSettings.user_id == user_id).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def save_for_user(self, user_id: UUID, provider: str, model: str) -> AgentUserSettings:
        existing = await self.get_for_user(user_id)
        now = datetime.now(timezone.utc)
        if existing is None:
            existing = AgentUserSettings(
                user_id=user_id,
                provider=provider,
                model=model,
                created_at=now,
                updated_at=now,
            )
        else:
            existing.provider = provider
            existing.model = model
            existing.updated_at = now

        self.session.add(existing)
        await self.session.commit()
        await self.session.refresh(existing)
        return existing
