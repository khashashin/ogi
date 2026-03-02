from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import Column, DateTime, Field, SQLModel


class UserPluginPreference(SQLModel, table=True):
    __tablename__ = "user_plugin_preferences"

    user_id: UUID = Field(primary_key=True, foreign_key="profiles.id", ondelete="CASCADE")
    plugin_name: str = Field(primary_key=True)
    enabled: bool = True
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )
