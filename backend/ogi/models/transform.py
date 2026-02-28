from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .entity import Entity, EntityType
from .edge import Edge


class TransformStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TransformResult(BaseModel):
    entities: list[Entity] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    messages: list[str] = Field(default_factory=list)
    ui_messages: list[str] = Field(default_factory=list)


class TransformRun(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    transform_name: str
    input_entity_id: UUID
    status: TransformStatus = TransformStatus.PENDING
    result: TransformResult | None = None
    error: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None


class TransformInfo(BaseModel):
    name: str
    display_name: str
    description: str
    input_types: list[EntityType]
    output_types: list[EntityType]
    category: str
