from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Column, Date, DateTime, Field, Integer, SQLModel, String, UniqueConstraint


class TelemetryTransformSnapshot(BaseModel):
    name: str
    version: str


class TelemetryMetricsSnapshot(BaseModel):
    projects_total: int = 0
    entities_total: int = 0
    edges_total: int = 0
    transform_runs_total: int = 0
    investigator_runs_total: int = 0
    active_users_total: int = 0


class TelemetryIngestPayload(BaseModel):
    instance_id: UUID
    instance_created_at: datetime | None = None
    ogi_version: str
    metric_date: date
    sent_at: datetime
    telemetry_level: Literal["basic", "full"]
    deployment_mode: Literal["cloud", "self-hosted"]
    metrics: TelemetryMetricsSnapshot | None = None
    installed_transforms: list[TelemetryTransformSnapshot] = PydanticField(default_factory=list)


class TelemetryLocalState(SQLModel, table=True):
    __tablename__ = "telemetry_local_state"

    id: int = Field(default=1, primary_key=True)
    instance_id: UUID = Field(index=True)
    instance_created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    last_basic_sent_on: date | None = Field(
        default=None,
        sa_column=Column(Date, nullable=True),
    )
    last_full_sent_on: date | None = Field(
        default=None,
        sa_column=Column(Date, nullable=True),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class TelemetryInstallation(SQLModel, table=True):
    __tablename__ = "telemetry_installations"

    instance_id: UUID = Field(primary_key=True)
    first_seen_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    last_seen_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    instance_created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    latest_ogi_version: str = Field(default="", sa_column=Column(String(length=64), nullable=False))
    latest_telemetry_level: str = Field(default="basic", sa_column=Column(String(length=16), nullable=False))
    deployment_mode: str = Field(default="self-hosted", sa_column=Column(String(length=32), nullable=False))
    latest_country_code: str | None = Field(default=None, sa_column=Column(String(length=8), nullable=True))


class TelemetryDailyMetric(SQLModel, table=True):
    __tablename__ = "telemetry_daily_metrics"
    __table_args__ = (UniqueConstraint("instance_id", "metric_date"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    instance_id: UUID = Field(foreign_key="telemetry_installations.instance_id", index=True, ondelete="CASCADE")
    metric_date: date = Field(sa_column=Column(Date, nullable=False))
    ogi_version: str = Field(default="", sa_column=Column(String(length=64), nullable=False))
    telemetry_level: str = Field(default="basic", sa_column=Column(String(length=16), nullable=False))
    deployment_mode: str = Field(default="self-hosted", sa_column=Column(String(length=32), nullable=False))
    country_code: str | None = Field(default=None, sa_column=Column(String(length=8), nullable=True))
    projects_total: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    entities_total: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    edges_total: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    transform_runs_total: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    investigator_runs_total: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    active_users_total: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class TelemetryInstalledTransform(SQLModel, table=True):
    __tablename__ = "telemetry_installed_transforms"
    __table_args__ = (UniqueConstraint("daily_metric_id", "transform_name"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    daily_metric_id: UUID = Field(
        foreign_key="telemetry_daily_metrics.id",
        index=True,
        ondelete="CASCADE",
    )
    transform_name: str = Field(sa_column=Column(String(length=255), nullable=False))
    transform_version: str = Field(default="", sa_column=Column(String(length=64), nullable=False))


class TelemetryInstanceSummary(BaseModel):
    instance_id: UUID
    first_seen_at: datetime
    last_seen_at: datetime
    instance_created_at: datetime | None
    latest_ogi_version: str
    latest_telemetry_level: str
    deployment_mode: str
    latest_country_code: str | None
    installed_transforms: list[TelemetryTransformSnapshot] = PydanticField(default_factory=list)


class TelemetryVersionCount(BaseModel):
    version: str
    count: int


class TelemetryOverviewResponse(BaseModel):
    active_instances_30d: int
    self_hosted_instances_30d: int
    cloud_instances_30d: int
    latest_metric_date: date | None
    recent_versions: list[TelemetryVersionCount]
