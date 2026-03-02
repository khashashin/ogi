from __future__ import annotations

from datetime import datetime, timezone
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from ogi.models.user_plugin_preference import UserPluginPreference

logger = logging.getLogger(__name__)


class UserPluginPreferenceStore:
    """Per-user plugin visibility/preferences."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_user(self, user_id: UUID) -> dict[str, bool]:
        try:
            stmt = select(UserPluginPreference).where(UserPluginPreference.user_id == user_id)
            result = await self.session.execute(stmt)
            rows = result.scalars().all()
            return {row.plugin_name: row.enabled for row in rows}
        except Exception:
            logger.exception("Failed to read user plugin preferences; defaulting to enabled")
            return {}

    async def is_enabled(self, user_id: UUID, plugin_name: str, default: bool = True) -> bool:
        try:
            stmt = select(UserPluginPreference).where(
                UserPluginPreference.user_id == user_id,
                UserPluginPreference.plugin_name == plugin_name,
            )
            result = await self.session.execute(stmt)
            pref = result.scalar_one_or_none()
            return pref.enabled if pref is not None else default
        except Exception:
            logger.exception("Failed to read plugin preference for '%s'", plugin_name)
            return default

    async def set_enabled(self, user_id: UUID, plugin_name: str, enabled: bool) -> None:
        try:
            stmt = select(UserPluginPreference).where(
                UserPluginPreference.user_id == user_id,
                UserPluginPreference.plugin_name == plugin_name,
            )
            result = await self.session.execute(stmt)
            pref = result.scalar_one_or_none()

            if pref is None:
                pref = UserPluginPreference(
                    user_id=user_id,
                    plugin_name=plugin_name,
                    enabled=enabled,
                )
            else:
                pref.enabled = enabled
                pref.updated_at = datetime.now(timezone.utc)

            self.session.add(pref)
            await self.session.commit()
        except Exception:
            logger.exception("Failed to update plugin preference for '%s'", plugin_name)
            await self.session.rollback()
