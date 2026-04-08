from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel, Column, JSON, DateTime


class ApiKeyRequirement(SQLModel):
    """Describes an API key needed by a transform."""
    service: str = ""
    description: str = ""
    env_var: str = ""


class TransformPermissions(SQLModel):
    """Safety permissions declared by a transform."""
    network: bool = False
    filesystem: bool = False
    subprocess: bool = False


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

    # Manifest metadata
    category: str = ""
    license: str = ""
    author_github: str = ""
    homepage: str = ""
    repository: str = ""
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    input_types: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    output_types: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    min_ogi_version: str = ""
    verification_tier: str = "community"  # official | verified | community | experimental
    api_keys_required: list[dict[str, str]] = Field(default_factory=list, sa_column=Column(JSON))
    python_dependencies: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    permissions: dict[str, bool] = Field(default_factory=dict, sa_column=Column(JSON))
    source: str = "local"  # local | registry | bundled
    registry_sha256: str = ""
    icon: str = ""
    color: str = ""

    # Runtime state
    transform_count: int = 0
    transform_names: list[str] = Field(default_factory=list, sa_column=Column(JSON))
