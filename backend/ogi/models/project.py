from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel, Column, DateTime


class Project(SQLModel, table=True):
    __tablename__ = "projects"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    description: str = ""
    owner_id: Optional[UUID] = Field(default=None, foreign_key="profiles.id", ondelete="SET NULL")
    is_public: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))


class ProjectBookmark(SQLModel, table=True):
    __tablename__ = "project_bookmarks"

    user_id: UUID = Field(primary_key=True, foreign_key="profiles.id", ondelete="CASCADE")
    project_id: UUID = Field(primary_key=True, foreign_key="projects.id", ondelete="CASCADE")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))


class ProjectCreate(SQLModel):
    name: str
    description: str = ""
    is_public: bool = False


class ProjectUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    is_public: bool | None = None


class ProjectDiscoverRead(SQLModel):
    id: UUID
    name: str
    description: str = ""
    owner_id: Optional[UUID] = None
    owner_name: str = ""
    is_public: bool = True
    created_at: datetime
    updated_at: datetime
    is_bookmarked: bool = False
