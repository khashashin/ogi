from __future__ import annotations

from datetime import datetime, timezone

from ogi.models import Entity, EntityType, TransformResult
from ogi.store.sun_store import SunStore
from ogi.store.timezone_store import TimezoneStore
from ogi.transforms.base import BaseTransform, TransformConfig, TransformSetting


class LocationToSunTimes(BaseTransform):
    name = "location_to_sun_times"
    display_name = "Location to Sun Times"
    description = "Adds sunrise, sunset, twilight, and daylight context for a location and date."
    input_types = [EntityType.LOCATION]
    output_types = [EntityType.LOCATION]
    category = "Location"
    long_description = (
        "Computes sunrise, sunset and civil twilight for a Location entity's coordinates "
        "on the date of a reference moment, calculated locally with the astral library "
        "rather than fetched from any external service. The reference moment is the Target "
        "Date/Time setting when supplied, otherwise the entity's observed_at property, "
        "otherwise the current UTC time. The timezone is taken from the entity's timezone "
        "property or, failing that, from a timezonefinder lookup on the coordinates, and "
        "times are written in local form when a zone is known and in UTC when it is not. "
        "Emits a single Location entity that adds daylight_at_reference_time, derived from "
        "the sun's elevation at the exact reference instant, together with sun_timezone, "
        "the sunrise and sunset values, the civil twilight begin and end values, and "
        "sun_polar_note when an event does not occur on that date. No edges are created "
        "and nothing is cached, because the calculation is deterministic."
    )
    when_to_use = (
        "Use this to test whether a claim or an image is consistent with the light at a "
        "place and time: whether a photo showing daylight could have been taken at the "
        "stated hour, whether a witness could have recognised a face at dusk, or whether "
        "an event described as after dark really was. Set Target Date/Time to the moment "
        "in question. Run Location to Geocode first for coordinates and Location to "
        "Timezone to pin the local clock, then pair this with Location to Weather Snapshot "
        "to check cloud cover and visibility at the same moment."
    )
    limitations = (
        "The result describes the geometric position of the sun for an observer at sea "
        "level, so terrain, buildings and altitude change the light actually seen, "
        "sometimes by many minutes in a valley or a dense city. Above the polar circles "
        "the sun may not rise or set on the date at all, in which case those fields are "
        "absent and sun_polar_note explains why. Events are computed for the local "
        "calendar date of the reference moment, so a time just after local midnight is "
        "measured against the new date. Coordinates are required: this transform does not "
        "geocode the entity value for you."
    )
    example_use_cases = [
        "Test whether a photo said to be shot in daylight at 19:00 is plausible for a date",
        "Check whether an incident described as after dark fell before or after civil dusk",
        "Establish the light conditions at a meeting point at the claimed meeting time",
    ]
    settings = [
        TransformSetting(
            name="target_datetime",
            display_name="Target Date/Time",
            description="Optional ISO-8601 timestamp to compute sun times for a specific moment. Overrides observed_at.",
            required=False,
            field_type="string",
        ),
    ]

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        props = dict(entity.properties or {})
        lat = self._to_float(props.get("lat"))
        lon = self._to_float(props.get("lon"))
        if lat is None or lon is None:
            return TransformResult(messages=["Sun-time lookup skipped: missing valid coordinates."])

        target_datetime_raw = config.settings.get("target_datetime", "")
        target_datetime = self._parse_datetime(target_datetime_raw)
        if target_datetime_raw.strip() and target_datetime is None:
            return TransformResult(messages=["Sun-time lookup skipped: invalid target_datetime. Use ISO-8601 format."])

        observed_at = self._parse_datetime(props.get("observed_at"))
        reference_time = target_datetime or observed_at or datetime.now(timezone.utc)

        timezone_name = self._timezone_name(props, lat, lon, reference_time)
        sun_result = SunStore().calculate(lat=lat, lon=lon, reference_time=reference_time, timezone_name=timezone_name)
        if sun_result.error:
            return TransformResult(messages=[sun_result.error])

        props["daylight_at_reference_time"] = sun_result.daylight_at_reference

        if sun_result.timezone:
            props["sun_timezone"] = sun_result.timezone
        if sun_result.sunrise_local:
            props["sunrise_local"] = sun_result.sunrise_local
        elif sun_result.sunrise_utc:
            props["sunrise_utc"] = sun_result.sunrise_utc
        if sun_result.sunset_local:
            props["sunset_local"] = sun_result.sunset_local
        elif sun_result.sunset_utc:
            props["sunset_utc"] = sun_result.sunset_utc
        if sun_result.civil_twilight_begin_local:
            props["civil_twilight_begin_local"] = sun_result.civil_twilight_begin_local
        elif sun_result.civil_twilight_begin_utc:
            props["civil_twilight_begin_utc"] = sun_result.civil_twilight_begin_utc
        if sun_result.civil_twilight_end_local:
            props["civil_twilight_end_local"] = sun_result.civil_twilight_end_local
        elif sun_result.civil_twilight_end_utc:
            props["civil_twilight_end_utc"] = sun_result.civil_twilight_end_utc
        if sun_result.polar_note:
            props["sun_polar_note"] = sun_result.polar_note

        phase = "day" if sun_result.daylight_at_reference else "night"
        messages = [
            f"Sun times calculated for {sun_result.date_local or sun_result.date_utc}.",
            f"Reference time is {phase}." if sun_result.daylight_at_reference is not None else "Reference daylight state unavailable.",
        ]
        if target_datetime is not None:
            messages.append(f"Requested timestamp: {target_datetime.isoformat()}.")
        elif observed_at is not None:
            messages.append(f"Observed timestamp: {observed_at.isoformat()}.")
        if sun_result.timezone:
            messages.append(f"Timezone: {sun_result.timezone}.")
        if sun_result.polar_note:
            messages.append(f"Polar conditions: {sun_result.polar_note}.")

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
    def _timezone_name(props: dict[str, object], lat: float, lon: float, reference_time: datetime) -> str | None:
        raw = props.get("timezone")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        resolution = TimezoneStore().resolve(lat, lon, reference_time)
        return resolution.timezone if resolution is not None else None

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
