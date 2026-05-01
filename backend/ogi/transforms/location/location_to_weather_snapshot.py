from __future__ import annotations

from datetime import datetime, timezone

from ogi.models import Entity, EntityType, TransformResult
from ogi.store.weather_store import WeatherStore
from ogi.transforms.base import BaseTransform, TransformConfig, TransformSetting


class LocationToWeatherSnapshot(BaseTransform):
    name = "location_to_weather_snapshot"
    display_name = "Location to Weather Snapshot"
    description = "Adds weather context for a location at the observed time or now."
    input_types = [EntityType.LOCATION]
    output_types = [EntityType.LOCATION]
    category = "Location"
    settings = [
        TransformSetting(
            name="openweather_api_key",
            display_name="OpenWeather API Key",
            description="API key for current and historical weather lookups.",
            required=True,
            field_type="secret",
        ),
    ]

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        props = dict(entity.properties or {})
        lat = self._to_float(props.get("lat"))
        lon = self._to_float(props.get("lon"))
        if lat is None or lon is None:
            return TransformResult(messages=["Weather lookup skipped: missing valid coordinates."])

        observed_at = self._parse_datetime(props.get("observed_at"))
        snapshot = await WeatherStore().get_snapshot(
            lat=lat,
            lon=lon,
            observed_at=observed_at,
            api_key=config.settings.get("openweather_api_key", "").strip(),
        )
        if snapshot.error:
            return TransformResult(messages=[snapshot.error])

        props["weather_condition"] = snapshot.condition
        props["weather_temp_c"] = snapshot.temp_c
        props["weather_wind_kph"] = snapshot.wind_kph
        props["weather_visibility_km"] = snapshot.visibility_km
        props["weather_source_timestamp"] = snapshot.source_timestamp

        summary = ", ".join(
            part
            for part in [
                snapshot.condition,
                f"{snapshot.temp_c:.1f} C" if snapshot.temp_c is not None else None,
                f"wind {snapshot.wind_kph:.1f} kph" if snapshot.wind_kph is not None else None,
                f"visibility {snapshot.visibility_km:.1f} km" if snapshot.visibility_km is not None else None,
            ]
            if part
        )
        messages = [
            f"Weather snapshot: {summary}." if summary else "Weather snapshot added.",
            "Used weather cache." if snapshot.cache_hit else "Used weather provider.",
        ]
        if snapshot.source_timestamp:
            messages.append(f"Source timestamp: {snapshot.source_timestamp}.")

        return TransformResult(
            entities=[
                Entity(
                    type=EntityType.LOCATION,
                    value=entity.value,
                    properties=props,
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
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return None
            try:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except ValueError:
                return None
        return None
