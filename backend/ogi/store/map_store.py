from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from ogi.models import (
    Edge,
    Entity,
    EntityType,
    GeocodeCache,
    MapCluster,
    MapPoint,
    MapPointsResponse,
    MapRoute,
    MapRoutesResponse,
)


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


def _extract_geo(properties: dict[str, Any], fallback_label: str | None = None) -> tuple[float | None, float | None, str | None, float | None]:
    lat = _to_float(properties.get("lat"))
    if lat is None:
        lat = _to_float(properties.get("latitude"))
    lon = _to_float(properties.get("lon"))
    if lon is None:
        lon = _to_float(properties.get("longitude"))

    label_raw = properties.get("location_label")
    label = label_raw.strip() if isinstance(label_raw, str) and label_raw.strip() else fallback_label
    confidence = _to_float(properties.get("geo_confidence"))
    return lat, lon, label, confidence


class MapStore:
    """Geospatial point/route extraction with geocode cache and clustering."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_points(
        self,
        project_id: UUID,
        cluster: bool = True,
        zoom: int = 3,
        geocode_missing: bool = True,
    ) -> MapPointsResponse:
        entities = list((await self.session.execute(select(Entity).where(Entity.project_id == project_id))).scalars().all())
        points: list[MapPoint] = []
        unresolved: list[str] = []

        for entity in entities:
            fallback = entity.value if entity.type == EntityType.LOCATION else None
            lat, lon, label, confidence = _extract_geo(entity.properties or {}, fallback)

            if lat is None or lon is None:
                if label:
                    cached = await self._get_cache(label)
                    if cached is None and geocode_missing:
                        cached = await self._geocode_and_cache(label)
                    if cached is not None:
                        lat = cached.lat
                        lon = cached.lon
                        if not label:
                            label = cached.display_name
                        if confidence is None:
                            confidence = cached.confidence
                if lat is None or lon is None:
                    if label:
                        unresolved.append(label)
                    continue
            elif label:
                await self._upsert_cache(label, lat, lon, confidence or 0.9, source="entity")

            points.append(
                MapPoint(
                    entity_id=entity.id,
                    entity_type=entity.type.value,
                    label=entity.value,
                    lat=float(lat),
                    lon=float(lon),
                    geo_confidence=confidence,
                    location_label=label,
                    source="entity",
                )
            )

        clusters = self._cluster_points(points, zoom) if cluster else []
        return MapPointsResponse(points=points, clusters=clusters, unresolved_labels=sorted(set(unresolved)))

    async def get_routes(self, project_id: UUID, geocode_missing: bool = True) -> MapRoutesResponse:
        points = await self.get_points(project_id, cluster=False, geocode_missing=geocode_missing)
        point_by_entity = {point.entity_id: point for point in points.points}
        edges = list((await self.session.execute(select(Edge).where(Edge.project_id == project_id))).scalars().all())

        routes: list[MapRoute] = []
        for edge in edges:
            src = point_by_entity.get(edge.source_id)
            dst = point_by_entity.get(edge.target_id)
            if src is None or dst is None:
                continue
            routes.append(
                MapRoute(
                    edge_id=edge.id,
                    source_entity_id=edge.source_id,
                    target_entity_id=edge.target_id,
                    source_lat=src.lat,
                    source_lon=src.lon,
                    target_lat=dst.lat,
                    target_lon=dst.lon,
                    label=edge.label,
                    weight=edge.weight,
                )
            )
        return MapRoutesResponse(routes=routes)

    async def _get_cache(self, query: str) -> GeocodeCache | None:
        normalized = query.strip().lower()
        if not normalized:
            return None
        stmt = select(GeocodeCache).where(GeocodeCache.query == normalized)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _upsert_cache(
        self,
        query: str,
        lat: float,
        lon: float,
        confidence: float,
        source: str,
        display_name: str = "",
    ) -> GeocodeCache:
        normalized = query.strip().lower()
        existing = await self._get_cache(normalized)
        now = datetime.now(timezone.utc)
        if existing:
            existing.lat = float(lat)
            existing.lon = float(lon)
            existing.confidence = float(confidence)
            existing.source = source
            if display_name:
                existing.display_name = display_name
            existing.updated_at = now
            self.session.add(existing)
            await self.session.commit()
            await self.session.refresh(existing)
            return existing

        row = GeocodeCache(
            query=normalized,
            lat=float(lat),
            lon=float(lon),
            confidence=float(confidence),
            source=source,
            display_name=display_name,
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def _geocode_and_cache(self, query: str) -> GeocodeCache | None:
        try:
            params = {"q": query, "format": "jsonv2", "limit": 1}
            headers = {"User-Agent": "OGI-Map-Geocoder/1.0"}
            async with httpx.AsyncClient(timeout=6) as client:
                resp = await client.get("https://nominatim.openstreetmap.org/search", params=params, headers=headers)
                resp.raise_for_status()
                payload = resp.json()
            if not payload:
                return None
            first = payload[0]
            lat = _to_float(first.get("lat"))
            lon = _to_float(first.get("lon"))
            if lat is None or lon is None:
                return None
            display_name = first.get("display_name", "") if isinstance(first.get("display_name"), str) else ""
            return await self._upsert_cache(query, lat, lon, confidence=0.6, source="nominatim", display_name=display_name)
        except Exception:
            return None

    @staticmethod
    def _cluster_points(points: list[MapPoint], zoom: int) -> list[MapCluster]:
        if not points:
            return []
        z = max(1, min(20, int(zoom)))
        cell = max(0.03, 2.4 / z)
        buckets: dict[tuple[int, int], list[MapPoint]] = {}
        for point in points:
            key = (int(point.lat / cell), int(point.lon / cell))
            buckets.setdefault(key, []).append(point)

        clusters: list[MapCluster] = []
        for (lat_key, lon_key), members in buckets.items():
            if len(members) <= 1:
                continue
            avg_lat = sum(m.lat for m in members) / len(members)
            avg_lon = sum(m.lon for m in members) / len(members)
            clusters.append(
                MapCluster(
                    cluster_id=f"{lat_key}:{lon_key}:{len(members)}",
                    lat=avg_lat,
                    lon=avg_lon,
                    count=len(members),
                    entity_ids=[m.entity_id for m in members],
                )
            )
        clusters.sort(key=lambda c: c.count, reverse=True)
        return clusters
