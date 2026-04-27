from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from ogi.models import (
    AuditLog,
    Edge,
    Entity,
    EntityType,
    LocationAggregate,
    ProjectEvent,
    TransformRun,
)


def _to_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _to_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _extract_temporal_geo(properties: dict[str, Any]) -> dict[str, object]:
    observed_at = _to_datetime(properties.get("observed_at"))
    valid_from = _to_datetime(properties.get("valid_from"))
    valid_to = _to_datetime(properties.get("valid_to"))

    lat = _to_float(properties.get("lat"))
    if lat is None:
        lat = _to_float(properties.get("latitude"))
    lon = _to_float(properties.get("lon"))
    if lon is None:
        lon = _to_float(properties.get("longitude"))

    location_label = properties.get("location_label")
    if not isinstance(location_label, str):
        location_label = None
    geo_confidence = _to_float(properties.get("geo_confidence"))

    return {
        "observed_at": observed_at,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "lat": lat,
        "lon": lon,
        "location_label": location_label,
        "geo_confidence": geo_confidence,
    }


class ProjectEventStore:
    """Project event aggregation and location normalization."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_events(
        self,
        project_id: UUID,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 200,
    ) -> list[ProjectEvent]:
        events: list[ProjectEvent] = []

        entity_stmt = select(Entity).where(Entity.project_id == project_id)
        edge_stmt = select(Edge).where(Edge.project_id == project_id)
        run_stmt = select(TransformRun).where(TransformRun.project_id == project_id)
        audit_stmt = select(AuditLog).where(AuditLog.project_id == project_id)

        entities = list((await self.session.execute(entity_stmt)).scalars().all())
        edges = list((await self.session.execute(edge_stmt)).scalars().all())
        runs = list((await self.session.execute(run_stmt)).scalars().all())
        audits = list((await self.session.execute(audit_stmt)).scalars().all())

        for entity in entities:
            temporal_geo = _extract_temporal_geo(entity.properties or {})
            events.append(
                ProjectEvent(
                    event_id=f"entity:{entity.id}",
                    event_type="entity_created",
                    project_id=project_id,
                    occurred_at=entity.created_at,
                    title=f"Entity created: {entity.type.value} {entity.value}",
                    entity_id=entity.id,
                    observed_at=temporal_geo["observed_at"],  # type: ignore[arg-type]
                    valid_from=temporal_geo["valid_from"],  # type: ignore[arg-type]
                    valid_to=temporal_geo["valid_to"],  # type: ignore[arg-type]
                    lat=temporal_geo["lat"],  # type: ignore[arg-type]
                    lon=temporal_geo["lon"],  # type: ignore[arg-type]
                    location_label=temporal_geo["location_label"],  # type: ignore[arg-type]
                    geo_confidence=temporal_geo["geo_confidence"],  # type: ignore[arg-type]
                    payload={"source": entity.source, "tags": entity.tags},
                )
            )

        for edge in edges:
            events.append(
                ProjectEvent(
                    event_id=f"edge:{edge.id}",
                    event_type="edge_created",
                    project_id=project_id,
                    occurred_at=edge.created_at,
                    title=f"Edge created: {edge.label or 'related_to'}",
                    edge_id=edge.id,
                    payload={
                        "source_id": str(edge.source_id),
                        "target_id": str(edge.target_id),
                        "source_transform": edge.source_transform,
                    },
                )
            )

        for run in runs:
            events.append(
                ProjectEvent(
                    event_id=f"transform:{run.id}",
                    event_type=f"transform_{run.status.value}",
                    project_id=project_id,
                    occurred_at=run.started_at,
                    title=f"Transform run: {run.transform_name} ({run.status.value})",
                    transform_run_id=run.id,
                    entity_id=run.input_entity_id,
                    payload={"error": run.error},
                )
            )

        for row in audits:
            events.append(
                ProjectEvent(
                    event_id=f"audit:{row.id}",
                    event_type="audit_log",
                    project_id=project_id,
                    occurred_at=row.created_at,
                    actor_user_id=row.actor_user_id,
                    title=f"Audit: {row.action}",
                    audit_log_id=row.id,
                    payload={
                        "action": row.action,
                        "resource_type": row.resource_type,
                        "resource_id": row.resource_id,
                        "details": row.details,
                    },
                )
            )

        filtered: list[ProjectEvent] = []
        for event in events:
            if since and event.occurred_at < since:
                continue
            if until and event.occurred_at > until:
                continue
            filtered.append(event)

        filtered.sort(key=lambda e: e.occurred_at, reverse=True)
        return filtered[:limit]

    async def list_locations(self, project_id: UUID, limit: int = 200) -> list[LocationAggregate]:
        stmt = select(Entity).where(Entity.project_id == project_id)
        entities = list((await self.session.execute(stmt)).scalars().all())

        grouped: dict[str, LocationAggregate] = {}
        for entity in entities:
            properties = entity.properties or {}
            temporal_geo = _extract_temporal_geo(properties)
            lat = temporal_geo["lat"]
            lon = temporal_geo["lon"]
            label = temporal_geo["location_label"]
            confidence = temporal_geo["geo_confidence"]

            if entity.type == EntityType.LOCATION and not label:
                label = entity.value
            if lat is None and lon is None and label is None:
                continue

            key = f"{label or ''}|{'' if lat is None else round(float(lat), 5)}|{'' if lon is None else round(float(lon), 5)}"
            row = grouped.get(key)
            if row is None:
                row = LocationAggregate(
                    key=key,
                    location_label=label if isinstance(label, str) else None,
                    lat=float(lat) if lat is not None else None,
                    lon=float(lon) if lon is not None else None,
                    geo_confidence=float(confidence) if confidence is not None else None,
                    entity_count=0,
                    entity_ids=[],
                )
                grouped[key] = row

            row.entity_count += 1
            row.entity_ids.append(entity.id)
            if row.geo_confidence is None and confidence is not None:
                row.geo_confidence = float(confidence)

        rows = list(grouped.values())
        rows.sort(key=lambda x: x.entity_count, reverse=True)
        return rows[:limit]
