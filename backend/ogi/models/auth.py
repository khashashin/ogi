from datetime import datetime, timezone
from uuid import UUID
from typing import Optional

from sqlmodel import SQLModel, Field, Column, DateTime

class UserProfile(SQLModel, table=True):
    __tablename__ = "profiles"
    
    id: UUID = Field(primary_key=True)
    email: str = ""
    display_name: str = ""
    avatar_url: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))


class ProjectMember(SQLModel, table=True):
    __tablename__ = "project_members"
    
    project_id: UUID = Field(primary_key=True, foreign_key="projects.id", ondelete="CASCADE")
    user_id: UUID = Field(primary_key=True, foreign_key="profiles.id", ondelete="CASCADE")
    role: str = "viewer"  # 'owner', 'editor', 'viewer'
    
    # We keep these for API responses but they aren't stored in this table directly
    # They will be populated by joins
    # TODO: Refactor API responses to separate DB model from Read model
    # For now we'll mark them as SA columns that don't exist, or just use property
    # Since we are migrating, we will recreate the Read model.

class ProjectMemberRead(SQLModel):
    project_id: UUID
    user_id: UUID
    role: str
    display_name: str = ""
    email: str = ""


class ProjectMemberCreate(SQLModel):
    email: str
    role: str = "editor"


class ProjectMemberUpdate(SQLModel):
    role: str
