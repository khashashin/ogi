from __future__ import annotations

from datetime import datetime

from ogi.models import Entity, EntityType, TransformResult
from ogi.store.location_search_store import LocationSearchStore
from ogi.store.timezone_store import TimezoneStore
from ogi.transforms.base import BaseTransform, TransformConfig


class LocationToTimezone(BaseTransform):
    name = "location_to_timezone"
    display_name = "Location to Timezone"
    description = "Resolves timezone context from location coordinates."
    input_types = [EntityType.LOCATION]
    output_types = [EntityType.LOCATION]
    category = "Location"

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        properties = dict(entity.properties or {})
        lat = self._to_float(properties.get("lat"))
        lon = self._to_float(properties.get("lon"))
        messages: list[str] = []

        if lat is None or lon is None:
            async for session in self._get_session():
                resolution = await LocationSearchStore(session).normalize(entity.value)
                break
            else:
                resolution = None

            if resolution is not None and resolution.lat is not None and resolution.lon is not None:
                lat = resolution.lat
                lon = resolution.lon
                properties["lat"] = lat
                properties["lon"] = lon
                if resolution.display_name:
                    properties["location_label"] = resolution.display_name
                if resolution.confidence is not None:
                    properties["geo_confidence"] = resolution.confidence
                messages.append("Coordinates were resolved via geocoding before timezone lookup.")

        if lat is None or lon is None:
            return TransformResult(messages=["Timezone lookup skipped: missing valid coordinates."])

        observed_at = self._parse_datetime(
            properties.get("observed_at") or properties.get("valid_from") or properties.get("timestamp")
        )
        store = TimezoneStore()
        resolution = store.resolve(lat, lon, observed_at=observed_at)
        if resolution is None:
            status = TimezoneStore.resolver_status()
            if status:
                return TransformResult(
                    messages=[f"Timezone lookup unavailable in this worker environment: {status}."]
                )
            return TransformResult(messages=["Unable to resolve timezone for the supplied coordinates."])

        properties["timezone"] = resolution.timezone
        properties["utc_offset"] = resolution.utc_offset
        properties["dst_active"] = resolution.dst_active
        if resolution.observed_utc_offset is not None:
            properties["observed_utc_offset"] = resolution.observed_utc_offset
        if resolution.observed_dst_active is not None:
            properties["observed_dst_active"] = resolution.observed_dst_active

        messages.extend(
            [
                f"Timezone: {resolution.timezone}.",
                f"UTC offset: {resolution.utc_offset}.",
                "DST is currently active." if resolution.dst_active else "DST is currently inactive.",
                "Used timezone cache." if resolution.cache_hit else "Used timezone resolver.",
            ]
        )

        return TransformResult(
            entities=[
                Entity(
                    type=EntityType.LOCATION,
                    value=entity.value,
                    properties=properties,
                    project_id=entity.project_id,
                    source=self.name,
                )
            ],
            messages=messages,
        )

    @staticmethod
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

    @staticmethod
    def _parse_datetime(value: object) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return None
            try:
                return datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None

    @staticmethod
    def _get_session():
        from ogi.db.database import get_session

        return get_session()
