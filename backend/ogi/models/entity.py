from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlmodel import Field, SQLModel, Column, JSON, DateTime


class EntityType(str, Enum):
    PERSON = "Person"
    USERNAME = "Username"
    VULNERABILITY = "Vulnerability"
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
    EntityType.USERNAME: {"icon": "at-sign", "color": "#ec4899", "category": "People"},
    EntityType.VULNERABILITY: {"icon": "shield-alert", "color": "#ef4444", "category": "Forensics"},
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


# Analyst-facing docs for each entity type, surfaced in the entity info dialog.
# Kept separate from ENTITY_TYPE_META so the registry's icon/color/category
# contract stays untouched.
ENTITY_TYPE_DOCS: dict[EntityType, dict[str, str]] = {
    EntityType.PERSON: {
        "description": (
            "A named individual. Person entities are the anchor of most people-centric "
            "investigations, and usually hold a full name rather than a handle."
        ),
        "usage": (
            "Start here when your subject is a human being and you want to branch out to "
            "the accounts, addresses, and organizations connected to them."
        ),
    },
    EntityType.USERNAME: {
        "description": (
            "A handle or screen name used to identify an account, independent of any "
            "single platform."
        ),
        "usage": (
            "Use this when you have a handle but do not yet know where it is registered. "
            "Username enumeration will suggest platforms, but treat every hit as a "
            "candidate until you confirm the same person owns it."
        ),
    },
    EntityType.VULNERABILITY: {
        "description": (
            "A specific known security weakness, normally identified by a CVE ID such as "
            "CVE-2025-12345."
        ),
        "usage": (
            "Add one when a scan, advisory, or banner points at a named flaw and you want "
            "its affected products, severity, and references pulled into the graph."
        ),
    },
    EntityType.DOMAIN: {
        "description": (
            "A registered domain name such as example.com, without a scheme or path."
        ),
        "usage": (
            "One of the most productive starting points in OSINT. From a domain you can "
            "reach hosting infrastructure, mail providers, certificates, subdomains, and "
            "registration records."
        ),
    },
    EntityType.IP_ADDRESS: {
        "description": "A single IPv4 or IPv6 address.",
        "usage": (
            "Use this to pivot from a name to the machine behind it. Beware that an "
            "address belonging to a CDN or shared host says little about any one site "
            "served from it."
        ),
    },
    EntityType.EMAIL_ADDRESS: {
        "description": "An email address in local-part@domain form.",
        "usage": (
            "A strong pivot: an address ties a person to a domain, and often to breach "
            "records and reused account handles elsewhere."
        ),
    },
    EntityType.PHONE_NUMBER: {
        "description": (
            "A telephone number, ideally stored in international E.164 form such as "
            "+41441234567."
        ),
        "usage": (
            "Use it to link a person or organization to a contactable line. A number "
            "found beside a name may still be a shared switchboard rather than a "
            "personal line."
        ),
    },
    EntityType.ORGANIZATION: {
        "description": "A company, institution, agency, or other formal group.",
        "usage": (
            "Add one to gather the people, domains, and infrastructure attributed to a "
            "single body, or when WHOIS and ASN records name a registrant."
        ),
    },
    EntityType.URL: {
        "description": "A single fully qualified web address, including scheme and path.",
        "usage": (
            "Use this when a specific page matters rather than the whole site. Fetching "
            "its content and mining that content for indicators is the usual next step."
        ),
    },
    EntityType.SOCIAL_MEDIA: {
        "description": (
            "A profile or account on a named social platform, as opposed to a bare "
            "handle."
        ),
        "usage": (
            "Add one once you have confirmed which platform an account lives on, then "
            "extract the identifiers and links published on the profile."
        ),
    },
    EntityType.HASH: {
        "description": (
            "A cryptographic digest of a file or artifact, typically MD5, SHA-1, or "
            "SHA-256."
        ),
        "usage": (
            "Use this to identify a file without possessing it, and to check reputation "
            "services for prior malware sightings of the same sample."
        ),
    },
    EntityType.DOCUMENT: {
        "description": (
            "A block of captured text or an attached artifact, often produced by a "
            "transform that summarizes what it found."
        ),
        "usage": (
            "Documents hold evidence in readable form. Mining one for indicators is the "
            "usual way to turn captured page text into further entities."
        ),
    },
    EntityType.LOCATION: {
        "description": (
            "A place: an address, a city, or a coordinate pair. Location entities carry "
            "latitude and longitude once geocoded, which is what puts them on the map."
        ),
        "usage": (
            "Add one to anchor an investigation geographically. Geocode it first so the "
            "map and the time, sun, and weather transforms have coordinates to work "
            "from."
        ),
    },
    EntityType.AS_NUMBER: {
        "description": (
            "An Autonomous System Number such as AS15169, identifying a network operator."
        ),
        "usage": (
            "Use this to group addresses by who actually routes them, which is often a "
            "better grouping than geography when mapping infrastructure."
        ),
    },
    EntityType.NETWORK: {
        "description": "An IP range or CIDR block such as 192.168.0.0/24.",
        "usage": (
            "Add one to represent an allocation rather than a single host, and to show "
            "that several addresses in the graph share a block."
        ),
    },
    EntityType.MX_RECORD: {
        "description": "A mail exchanger record naming the host that accepts a domain's mail.",
        "usage": (
            "Reveals who really handles mail for a domain. Self-hosted mail and a hosted "
            "provider or filtering gateway look very different here."
        ),
    },
    EntityType.NS_RECORD: {
        "description": "A nameserver record delegating DNS authority for a domain.",
        "usage": (
            "Use it to identify the DNS provider, and to spot unrelated-looking domains "
            "that quietly share the same delegation."
        ),
    },
    EntityType.NAMESERVER: {
        "description": "A DNS nameserver host that answers authoritatively for a zone.",
        "usage": (
            "Treat a shared nameserver as a weak link between domains: common providers "
            "host enormous numbers of unrelated zones."
        ),
    },
    EntityType.SSL_CERTIFICATE: {
        "description": (
            "A TLS certificate, carrying its issuer, subject, validity dates, and "
            "alternative names."
        ),
        "usage": (
            "Certificates leak infrastructure. Subject alternative names routinely "
            "expose internal or forgotten hostnames belonging to the same operator."
        ),
    },
    EntityType.SUBDOMAIN: {
        "description": "A host beneath a parent domain, such as api.example.com.",
        "usage": (
            "Subdomains are where staging, admin, and legacy services hide. Resolve the "
            "interesting ones to addresses to see which are actually live."
        ),
    },
    EntityType.HTTP_HEADER: {
        "description": "A single HTTP response header name and value observed on a URL.",
        "usage": (
            "Headers fingerprint the server and its stack, though values are trivially "
            "spoofed and a CDN's headers describe the CDN rather than the origin."
        ),
    },
}


class EntityTypeTransformRef(SQLModel):
    """A transform referenced from the entity type documentation dialog."""

    name: str
    display_name: str
    description: str
    category: str = ""
    api_key_services: list[str] = Field(default_factory=list)
    plugin_name: str | None = None


class EntityTypeDocumentation(SQLModel):
    """What an entity type represents, and how transforms connect to it."""

    type: EntityType
    category: str = ""
    icon: str = ""
    color: str = ""
    description: str = ""
    usage: str = ""
    consumed_by: list[EntityTypeTransformRef] = Field(default_factory=list)
    produced_by: list[EntityTypeTransformRef] = Field(default_factory=list)


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
    origin_source: str = "manual"
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
    origin_source: str | None = None


class EntityUpdate(SQLModel):
    value: str | None = None
    properties: dict[str, Any] | None = None
    icon: str | None = None
    weight: int | None = None
    notes: str | None = None
    tags: list[str] | None = None
