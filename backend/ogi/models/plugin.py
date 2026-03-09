from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel, Column, JSON, DateTime


class PluginInfo(SQLModel, table=True):
    __tablename__ = "plugins"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    version: str = ""
    display_name: str = ""
    description: str = ""
    author: str = ""
    enabled: bool = True
    installed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
    
    # Internal state properties (not saved in the db)
    transform_count: int = 0
    transform_names: list[str] = Field(default_factory=list, sa_column=Column(JSON))
