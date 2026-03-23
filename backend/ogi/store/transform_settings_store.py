from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from ogi.models.transform_settings import GlobalTransformSetting, UserTransformSetting


class TransformSettingsStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_global(self, transform_name: str) -> dict[str, str]:
        stmt = select(GlobalTransformSetting).where(GlobalTransformSetting.transform_name == transform_name)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        return dict(row.settings) if row else {}

    async def set_global(self, transform_name: str, settings: dict[str, str]) -> None:
        stmt = select(GlobalTransformSetting).where(GlobalTransformSetting.transform_name == transform_name)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            row = GlobalTransformSetting(transform_name=transform_name, settings=settings)
        else:
            row.settings = settings
            row.updated_at = datetime.now(timezone.utc)
        self.session.add(row)
        await self.session.commit()

    async def get_user(self, user_id: UUID, transform_name: str) -> dict[str, str]:
        stmt = select(UserTransformSetting).where(
            UserTransformSetting.user_id == user_id,
            UserTransformSetting.transform_name == transform_name,
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        return dict(row.settings) if row else {}

    async def set_user(self, user_id: UUID, transform_name: str, settings: dict[str, str]) -> None:
        stmt = select(UserTransformSetting).where(
            UserTransformSetting.user_id == user_id,
            UserTransformSetting.transform_name == transform_name,
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            row = UserTransformSetting(user_id=user_id, transform_name=transform_name, settings=settings)
        else:
            row.settings = settings
            row.updated_at = datetime.now(timezone.utc)
        self.session.add(row)
        await self.session.commit()

