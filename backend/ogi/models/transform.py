from typing import Any, Optional
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlmodel import Field, SQLModel, Column, JSON, DateTime, String

from .entity import Entity, EntityType
from .edge import Edge


class TransformStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TransformResult(SQLModel):
    entities: list[Entity] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    messages: list[str] = Field(default_factory=list)
    ui_messages: list[str] = Field(default_factory=list)


class TransformRun(SQLModel, table=True):
    __tablename__ = "transform_runs"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    project_id: UUID = Field(foreign_key="projects.id", ondelete="CASCADE")
    transform_name: str
    input_entity_id: UUID
    status: TransformStatus = TransformStatus.PENDING
    result: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    error: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column("created_at", DateTime(timezone=True)))
    completed_at: datetime | None = Field(default=None, sa_column=Column("completed_at", DateTime(timezone=True), nullable=True))

class TransformJobMessage(BaseModel):
    """Message published via Redis pub/sub when a transform job changes state."""
    type: str  # "job_submitted" | "job_started" | "job_completed" | "job_failed" | "job_cancelled"
    job_id: UUID
    project_id: UUID
    transform_name: str
    input_entity_id: UUID
    progress: float | None = None
    message: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    timestamp: datetime


class TransformInfo(SQLModel):
    name: str
    display_name: str
    description: str
    input_types: list[EntityType]
    output_types: list[EntityType]
    category: str
    api_key_services: list[str] = Field(default_factory=list)
    plugin_name: str | None = None
    plugin_verification_tier: str | None = None
    plugin_permissions: dict[str, bool] = Field(default_factory=dict)
    plugin_source: str | None = None
    settings: list[dict[str, object]] = Field(default_factory=list)


class TransformDocumentation(SQLModel):
    """Long-form docs for a single transform, served on demand.

    Kept out of :class:`TransformInfo` so the per-entity transform list stays
    small; the README alone can be several KB per plugin.
    """

    name: str
    display_name: str
    description: str
    long_description: str = ""
    when_to_use: str = ""
    limitations: str = ""
    example_use_cases: list[str] = Field(default_factory=list)
    input_types: list[EntityType] = Field(default_factory=list)
    output_types: list[EntityType] = Field(default_factory=list)
    category: str = ""
    api_key_services: list[str] = Field(default_factory=list)
    setting_names: list[str] = Field(default_factory=list)
    source: str = "builtin"  # builtin | plugin
    plugin_name: str | None = None
    plugin_version: str = ""
    plugin_author: str = ""
    plugin_verification_tier: str | None = None
    plugin_homepage: str = ""
    plugin_repository: str = ""
    readme: str = ""
