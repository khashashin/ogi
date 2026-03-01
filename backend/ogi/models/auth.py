from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    id: UUID
    email: str = ""
    display_name: str = ""
    avatar_url: str = ""


class ProjectMember(BaseModel):
    project_id: UUID
    user_id: UUID
    role: str = "viewer"  # 'owner', 'editor', 'viewer'
    display_name: str = ""
    email: str = ""


class ProjectMemberCreate(BaseModel):
    email: str
    role: str = "editor"


class ProjectMemberUpdate(BaseModel):
    role: str
