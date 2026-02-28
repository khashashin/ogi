from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Project(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    description: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
