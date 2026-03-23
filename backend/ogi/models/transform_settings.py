from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Column, DateTime, Field, JSON, SQLModel


class GlobalTransformSetting(SQLModel, table=True):
    __tablename__ = "global_transform_settings"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    transform_name: str = Field(unique=True, index=True)
    settings: dict[str, str] = Field(default_factory=dict, sa_column=Column(JSON))
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )


class UserTransformSetting(SQLModel, table=True):
    __tablename__ = "user_transform_settings"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="profiles.id", ondelete="CASCADE", index=True)
    transform_name: str = Field(index=True)
    settings: dict[str, str] = Field(default_factory=dict, sa_column=Column(JSON))
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )

