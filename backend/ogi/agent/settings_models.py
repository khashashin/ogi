from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlmodel import Column, DateTime, Field, SQLModel


class AgentSettingsRead(BaseModel):
    provider: str
    model: str
    has_api_key: bool


class AgentSettingsUpdate(BaseModel):
    provider: str
    model: str


class AgentModelOption(BaseModel):
    id: str
    label: str
    source: str


class AgentModelCatalog(BaseModel):
    provider: str
    default_model: str
    recommended_models: list[AgentModelOption]
    available_models: list[AgentModelOption]
    has_api_key: bool


class AgentSettingsTestRequest(BaseModel):
    provider: str
    model: str


class AgentSettingsTestResult(BaseModel):
    provider: str
    model: str
    success: bool
    has_api_key: bool
    model_found: bool
    message: str
    available_models: list[AgentModelOption] = []


class AgentUserSettings(SQLModel, table=True):
    __tablename__ = "agent_user_settings"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="profiles.id", ondelete="CASCADE", index=True, unique=True)
    provider: str = Field(default="")
    model: str = Field(default="")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )
