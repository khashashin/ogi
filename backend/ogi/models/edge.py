from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Edge(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source_id: UUID
    target_id: UUID
    label: str = ""
    weight: int = 1
    properties: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    bidirectional: bool = False
    source_transform: str = ""
    project_id: UUID | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EdgeCreate(BaseModel):
    source_id: UUID
    target_id: UUID
    label: str = ""
    weight: int = 1
    properties: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    bidirectional: bool = False
    source_transform: str = ""
