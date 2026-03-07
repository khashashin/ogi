from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from pydantic import BaseModel


class TimezoneResolution(BaseModel):
    timezone: str
    utc_offset: str
    dst_active: bool
    cache_hit: bool = False
    observed_utc_offset: str | None = None
    observed_dst_active: bool | None = None


class TimezoneStore:
    """Resolve timezone context from coordinates with lightweight cell caching."""

    _cell_cache: dict[str, str] = {}
    _resolver: object | None = None
    _resolver_import_error: str | None = None

    def resolve(self, lat: float, lon: float, observed_at: datetime | None = None) -> TimezoneResolution | None:
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            return None

        cell = self._cell_key(lat, lon)
        tz_name = self._cell_cache.get(cell)
        cache_hit = tz_name is not None
        if tz_name is None:
            tz_name = self._resolve_timezone_name(lat, lon)
            if not tz_name:
                return None
            self._cell_cache[cell] = tz_name

        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            return None

        now_local = datetime.now(timezone.utc).astimezone(tz)
        resolution = TimezoneResolution(
            timezone=tz_name,
            utc_offset=self._format_offset(now_local),
            dst_active=bool(now_local.dst() and now_local.dst().total_seconds() != 0),
            cache_hit=cache_hit,
        )

        if observed_at is not None:
            observed_local = observed_at.astimezone(tz)
            resolution.observed_utc_offset = self._format_offset(observed_local)
            resolution.observed_dst_active = bool(
                observed_local.dst() and observed_local.dst().total_seconds() != 0
            )

        return resolution

    @classmethod
    def _cell_key(cls, lat: float, lon: float) -> str:
        return f"{round(lat, 2):.2f}:{round(lon, 2):.2f}"

    @classmethod
    def _resolve_timezone_name(cls, lat: float, lon: float) -> str | None:
        try:
            if cls._resolver is None:
                from timezonefinder import TimezoneFinder  # type: ignore[import-not-found]

                cls._resolver = TimezoneFinder()
                cls._resolver_import_error = None

            resolver = cls._resolver
            tz_name = resolver.timezone_at(lat=lat, lng=lon)
            if not tz_name:
                tz_name = resolver.certain_timezone_at(lat=lat, lng=lon)
            if isinstance(tz_name, str) and tz_name.strip():
                return tz_name.strip()
        except Exception as exc:
            if cls._resolver is None:
                cls._resolver_import_error = str(exc)
            return None
        return None

    @classmethod
    def resolver_status(cls) -> str | None:
        return cls._resolver_import_error

    @staticmethod
    def _format_offset(value: datetime) -> str:
        offset = value.utcoffset()
        if offset is None:
            return "+00:00"
        total_minutes = int(offset.total_seconds() // 60)
        sign = "+" if total_minutes >= 0 else "-"
        total_minutes = abs(total_minutes)
        hours, minutes = divmod(total_minutes, 60)
        return f"{sign}{hours:02d}:{minutes:02d}"
