from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlmodel import Column, DateTime, Field, JSON, SQLModel


class TemporalGeoConventions(SQLModel):
    observed_at: str = "ISO-8601 timestamp when this observation was seen"
    valid_from: str = "ISO-8601 timestamp when this information became valid"
    valid_to: str = "ISO-8601 timestamp when this information stops being valid"
    lat: str = "Latitude in decimal degrees"
    lon: str = "Longitude in decimal degrees"
    location_label: str = "Human-readable location label"
    geo_confidence: str = "Confidence [0.0-1.0] for geospatial extraction"


class ProjectEvent(SQLModel):
    event_id: str
    event_type: str
    project_id: UUID
    occurred_at: datetime
    actor_user_id: UUID | None = None
    title: str
    entity_id: UUID | None = None
    edge_id: UUID | None = None
    transform_run_id: UUID | None = None
    audit_log_id: UUID | None = None
    observed_at: datetime | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    lat: float | None = None
    lon: float | None = None
    location_label: str | None = None
    geo_confidence: float | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ProjectEventsResponse(SQLModel):
    conventions: TemporalGeoConventions
    items: list[ProjectEvent]


class LocationAggregate(SQLModel):
    key: str
    location_label: str | None = None
    lat: float | None = None
    lon: float | None = None
    geo_confidence: float | None = None
    entity_count: int = 0
    entity_ids: list[UUID] = Field(default_factory=list)


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    project_id: UUID = Field(foreign_key="projects.id", ondelete="CASCADE")
    actor_user_id: UUID | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )


class AuditLogCreate(SQLModel):
    action: str
    resource_type: str
    resource_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
