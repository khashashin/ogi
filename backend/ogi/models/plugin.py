from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PluginInfo(BaseModel):
    name: str
    version: str = ""
    display_name: str = ""
    description: str = ""
    author: str = ""
    enabled: bool = True
    transform_count: int = 0
    transform_names: list[str] = Field(default_factory=list)
