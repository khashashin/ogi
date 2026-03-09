from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlmodel import Field, SQLModel, Column, JSON, DateTime


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
    SSL_CERTIFICATE = "SSLCertificate"
    SUBDOMAIN = "Subdomain"
    HTTP_HEADER = "HTTPHeader"


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
    EntityType.SSL_CERTIFICATE: {"icon": "shield", "color": "#10b981", "category": "Infrastructure"},
    EntityType.SUBDOMAIN: {"icon": "globe", "color": "#06b6d4", "category": "Infrastructure"},
    EntityType.HTTP_HEADER: {"icon": "file-code", "color": "#8b5cf6", "category": "Forensics"},
}


class Entity(SQLModel, table=True):
    __tablename__ = "entities"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    type: EntityType
    value: str
    properties: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    icon: str = ""
    weight: int = 1
    notes: str = ""
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    source: str = "manual"
    project_id: UUID = Field(foreign_key="projects.id", ondelete="CASCADE")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True)))

    def model_post_init(self, _context: object) -> None:
        if not self.icon:
            meta = ENTITY_TYPE_META.get(self.type)
            if meta:
                self.icon = meta["icon"]


class EntityCreate(SQLModel):
    type: EntityType
    value: str
    properties: dict[str, Any] = Field(default_factory=dict)
    weight: int = 1
    notes: str = ""
    tags: list[str] = Field(default_factory=list)
    source: str = "manual"


class EntityUpdate(SQLModel):
    value: str | None = None
    properties: dict[str, Any] | None = None
    weight: int | None = None
    notes: str | None = None
    tags: list[str] | None = None
