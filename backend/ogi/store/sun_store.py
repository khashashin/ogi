from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from pydantic import BaseModel


class SunTimesResult(BaseModel):
    date_utc: str
    date_local: str | None = None
    timezone: str | None = None
    reference_time_utc: str
    reference_time_local: str | None = None
    sunrise_utc: str | None = None
    sunrise_local: str | None = None
    sunset_utc: str | None = None
    sunset_local: str | None = None
    civil_twilight_begin_utc: str | None = None
    civil_twilight_begin_local: str | None = None
    civil_twilight_end_utc: str | None = None
    civil_twilight_end_local: str | None = None
    nautical_twilight_begin_utc: str | None = None
    nautical_twilight_begin_local: str | None = None
    nautical_twilight_end_utc: str | None = None
    nautical_twilight_end_local: str | None = None
    astronomical_twilight_begin_utc: str | None = None
    astronomical_twilight_begin_local: str | None = None
    astronomical_twilight_end_utc: str | None = None
    astronomical_twilight_end_local: str | None = None
    daylight_at_reference: bool | None = None
    polar_note: str | None = None
    error: str | None = None


class SunStore:
    """Deterministic sunrise/sunset/twilight calculations for a coordinate/date."""

    def calculate(
        self,
        lat: float,
        lon: float,
        reference_time: datetime,
        timezone_name: str | None = None,
    ) -> SunTimesResult:
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            return SunTimesResult(
                date_utc=reference_time.astimezone(timezone.utc).date().isoformat(),
                reference_time_utc=reference_time.astimezone(timezone.utc).isoformat(),
                error="Sun-time lookup skipped: invalid coordinates.",
            )

        try:
            from astral import Observer
            from astral.sun import dawn, dusk, elevation, sunrise, sunset
        except Exception:
            return SunTimesResult(
                date_utc=reference_time.astimezone(timezone.utc).date().isoformat(),
                reference_time_utc=reference_time.astimezone(timezone.utc).isoformat(),
                error="Sun-time calculation support is unavailable.",
            )

        ref_utc = reference_time.astimezone(timezone.utc)
        tz = self._resolve_timezone(timezone_name)
        ref_local = ref_utc.astimezone(tz) if tz is not None else None
        local_date = ref_local.date() if ref_local is not None else ref_utc.date()

        observer = Observer(latitude=lat, longitude=lon)
        polar_notes: list[str] = []

        def capture(label: str, fn, *, event_date: date, tzinfo, **kwargs) -> datetime | None:
            try:
                return fn(observer, date=event_date, tzinfo=tzinfo, **kwargs)
            except ValueError as exc:
                polar_notes.append(f"{label}: {exc}")
                return None

        result = SunTimesResult(
            date_utc=ref_utc.date().isoformat(),
            date_local=local_date.isoformat() if ref_local is not None else None,
            timezone=timezone_name if tz is not None else None,
            reference_time_utc=ref_utc.isoformat(),
            reference_time_local=ref_local.isoformat() if ref_local is not None else None,
        )

        sunrise_utc = capture("sunrise", sunrise, event_date=local_date, tzinfo=timezone.utc)
        sunset_utc = capture("sunset", sunset, event_date=local_date, tzinfo=timezone.utc)
        civil_begin_utc = capture("civil dawn", dawn, event_date=local_date, tzinfo=timezone.utc, depression=6)
        civil_end_utc = capture("civil dusk", dusk, event_date=local_date, tzinfo=timezone.utc, depression=6)
        nautical_begin_utc = capture("nautical dawn", dawn, event_date=local_date, tzinfo=timezone.utc, depression=12)
        nautical_end_utc = capture("nautical dusk", dusk, event_date=local_date, tzinfo=timezone.utc, depression=12)
        astro_begin_utc = capture("astronomical dawn", dawn, event_date=local_date, tzinfo=timezone.utc, depression=18)
        astro_end_utc = capture("astronomical dusk", dusk, event_date=local_date, tzinfo=timezone.utc, depression=18)

        result.sunrise_utc = self._to_iso(sunrise_utc)
        result.sunset_utc = self._to_iso(sunset_utc)
        result.civil_twilight_begin_utc = self._to_iso(civil_begin_utc)
        result.civil_twilight_end_utc = self._to_iso(civil_end_utc)
        result.nautical_twilight_begin_utc = self._to_iso(nautical_begin_utc)
        result.nautical_twilight_end_utc = self._to_iso(nautical_end_utc)
        result.astronomical_twilight_begin_utc = self._to_iso(astro_begin_utc)
        result.astronomical_twilight_end_utc = self._to_iso(astro_end_utc)

        if tz is not None:
            result.sunrise_local = self._to_iso_local(sunrise_utc, tz)
            result.sunset_local = self._to_iso_local(sunset_utc, tz)
            result.civil_twilight_begin_local = self._to_iso_local(civil_begin_utc, tz)
            result.civil_twilight_end_local = self._to_iso_local(civil_end_utc, tz)
            result.nautical_twilight_begin_local = self._to_iso_local(nautical_begin_utc, tz)
            result.nautical_twilight_end_local = self._to_iso_local(nautical_end_utc, tz)
            result.astronomical_twilight_begin_local = self._to_iso_local(astro_begin_utc, tz)
            result.astronomical_twilight_end_local = self._to_iso_local(astro_end_utc, tz)

        try:
            result.daylight_at_reference = elevation(observer, ref_utc) > 0
        except Exception:
            result.daylight_at_reference = None

        if polar_notes:
            result.polar_note = "; ".join(polar_notes)

        return result

    @staticmethod
    def _resolve_timezone(timezone_name: str | None) -> ZoneInfo | None:
        if not timezone_name:
            return None
        try:
            return ZoneInfo(timezone_name)
        except Exception:
            return None

    @staticmethod
    def _to_iso(value: datetime | None) -> str | None:
        return value.astimezone(timezone.utc).isoformat() if value is not None else None

    @staticmethod
    def _to_iso_local(value: datetime | None, tz: ZoneInfo) -> str | None:
        return value.astimezone(tz).isoformat() if value is not None else None
