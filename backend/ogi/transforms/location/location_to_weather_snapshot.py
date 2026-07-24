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
    long_description = (
        "Fetches weather conditions for a Location entity's coordinates from OpenWeather "
        "and writes them onto a single new Location entity as weather_condition, "
        "weather_temp_c, weather_wind_kph, weather_visibility_km and "
        "weather_source_timestamp. With no timestamp available it calls the current "
        "weather endpoint; when the Target Date/Time setting or the entity's observed_at "
        "property supplies a moment, it calls the One Call time-machine endpoint for that "
        "moment instead, with the setting taking priority over the property. An "
        "OpenWeather API key is required and is supplied as a transform setting. Wind is "
        "converted to kilometres per hour and visibility to kilometres. Results are held "
        "in an in-memory cache keyed on the coordinates rounded to two decimals and the "
        "hour of the requested time, and the run messages state whether the cache or the "
        "provider answered. No edges are created."
    )
    when_to_use = (
        "Use this to corroborate or challenge an account of what happened at a place and "
        "time: whether a photo showing wet streets or clear skies matches the conditions "
        "recorded there, whether a claimed sighting was possible in the visibility of that "
        "moment, or whether the weather supports an alibi. Set Target Date/Time to the "
        "moment in question. Run Location to Geocode first if the entity lacks "
        "coordinates, and pair this with Location to Sun Times to establish the light as "
        "well as the weather."
    )
    limitations = (
        "Historical lookups use the One Call time-machine endpoint, which free OpenWeather "
        "plans do not include; without a suitable subscription the transform reports that "
        "history is unavailable for the key or plan, and coverage thins out for older "
        "dates and remote areas. Readings are modelled or interpolated from nearby "
        "stations rather than measured at the exact point. Both the provider data and the "
        "cache bucket resolve to the hour, so short showers and minute-level changes do "
        "not show. The cache also rounds coordinates to two decimals, so points within "
        "about a kilometre share one snapshot."
    )
    example_use_cases = [
        "Check whether the weather in a photo matches the claimed place and time",
        "Test an alibi that depends on a storm, fog or snowfall at a specific location",
        "Establish visibility at the time a witness claims to have seen something",
    ]
    settings = [
        TransformSetting(
            name="openweather_api_key",
            display_name="OpenWeather API Key",
            description="API key for current and historical weather lookups.",
            required=True,
            field_type="secret",
        ),
        TransformSetting(
            name="target_datetime",
            display_name="Target Date/Time",
            description="Optional ISO-8601 timestamp to fetch weather for a specific moment. Overrides observed_at.",
            required=False,
            field_type="string",
        ),
    ]

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        props = dict(entity.properties or {})
        lat = self._to_float(props.get("lat"))
        lon = self._to_float(props.get("lon"))
        if lat is None or lon is None:
            return TransformResult(messages=["Weather lookup skipped: missing valid coordinates."])

        target_datetime_raw = config.settings.get("target_datetime", "")
        target_datetime = self._parse_datetime(target_datetime_raw)
        if target_datetime_raw.strip() and target_datetime is None:
            return TransformResult(messages=["Weather lookup skipped: invalid target_datetime. Use ISO-8601 format."])

        observed_at = self._parse_datetime(props.get("observed_at"))
        lookup_time = target_datetime or observed_at
        snapshot = await WeatherStore().get_snapshot(
            lat=lat,
            lon=lon,
            observed_at=lookup_time,
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
        if target_datetime is not None:
            messages.append(f"Requested timestamp: {target_datetime.isoformat()}.")
        elif observed_at is not None:
            messages.append(f"Observed timestamp: {observed_at.isoformat()}.")
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
