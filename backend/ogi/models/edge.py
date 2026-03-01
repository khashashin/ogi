from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlmodel import Field, SQLModel, Column, JSON, DateTime


class Edge(SQLModel, table=True):
    __tablename__ = "edges"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    source_id: UUID = Field(foreign_key="entities.id", ondelete="CASCADE")
    target_id: UUID = Field(foreign_key="entities.id", ondelete="CASCADE")
    label: str = ""
    weight: int = 1
    properties: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    bidirectional: bool = False
    source_transform: str = ""
    project_id: UUID = Field(foreign_key="projects.id", ondelete="CASCADE")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))


class EdgeCreate(SQLModel):
    source_id: UUID
    target_id: UUID
    label: str = ""
    weight: int = 1
    properties: dict[str, Any] = Field(default_factory=dict)
    bidirectional: bool = False
    source_transform: str = ""


class EdgeUpdate(SQLModel):
    label: str | None = None
    weight: int | None = None
    properties: dict[str, Any] | None = None
