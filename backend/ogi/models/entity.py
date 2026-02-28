from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EntityType(str, Enum):
    PERSON = "Person"
    DOMAIN = "Domain"
    IP_ADDRESS = "IPAddress"
    EMAIL_ADDRESS = "EmailAddress"
    PHONE_NUMBER = "PhoneNumber"
    ORGANIZATION = "Organization"
    URL = "URL"
    SOCIAL_MEDIA = "SocialMedia"
    HASH = "Hash"
    DOCUMENT = "Document"
    LOCATION = "Location"
    AS_NUMBER = "ASNumber"
    NETWORK = "Network"
    MX_RECORD = "MXRecord"
    NS_RECORD = "NSRecord"
    NAMESERVER = "Nameserver"


ENTITY_TYPE_META: dict[EntityType, dict[str, str]] = {
    EntityType.PERSON: {"icon": "user", "color": "#6366f1", "category": "People"},
    EntityType.DOMAIN: {"icon": "globe", "color": "#22d3ee", "category": "Infrastructure"},
    EntityType.IP_ADDRESS: {"icon": "server", "color": "#f59e0b", "category": "Infrastructure"},
    EntityType.EMAIL_ADDRESS: {"icon": "mail", "color": "#a78bfa", "category": "People"},
    EntityType.PHONE_NUMBER: {"icon": "phone", "color": "#34d399", "category": "People"},
    EntityType.ORGANIZATION: {"icon": "building", "color": "#fb923c", "category": "People"},
    EntityType.URL: {"icon": "link", "color": "#60a5fa", "category": "Infrastructure"},
    EntityType.SOCIAL_MEDIA: {"icon": "at-sign", "color": "#f472b6", "category": "People"},
    EntityType.HASH: {"icon": "hash", "color": "#94a3b8", "category": "Forensics"},
    EntityType.DOCUMENT: {"icon": "file-text", "color": "#e2e8f0", "category": "Forensics"},
    EntityType.LOCATION: {"icon": "map-pin", "color": "#4ade80", "category": "Location"},
    EntityType.AS_NUMBER: {"icon": "network", "color": "#fbbf24", "category": "Infrastructure"},
    EntityType.NETWORK: {"icon": "wifi", "color": "#38bdf8", "category": "Infrastructure"},
    EntityType.MX_RECORD: {"icon": "mail", "color": "#c084fc", "category": "Infrastructure"},
    EntityType.NS_RECORD: {"icon": "server", "color": "#67e8f9", "category": "Infrastructure"},
    EntityType.NAMESERVER: {"icon": "server", "color": "#2dd4bf", "category": "Infrastructure"},
}


class Entity(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    type: EntityType
    value: str
    properties: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    icon: str = ""
    weight: int = 1
    notes: str = ""
    tags: list[str] = Field(default_factory=list)
    source: str = "manual"
    project_id: UUID | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def model_post_init(self, _context: object) -> None:
        if not self.icon:
            meta = ENTITY_TYPE_META.get(self.type)
            if meta:
                self.icon = meta["icon"]


class EntityCreate(BaseModel):
    type: EntityType
    value: str
    properties: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    weight: int = 1
    notes: str = ""
    tags: list[str] = Field(default_factory=list)
    source: str = "manual"


class EntityUpdate(BaseModel):
    value: str | None = None
    properties: dict[str, str | int | float | bool | None] | None = None
    weight: int | None = None
    notes: str | None = None
    tags: list[str] | None = None
