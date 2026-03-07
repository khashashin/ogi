from __future__ import annotations

from datetime import datetime, timezone

import httpx
from pydantic import BaseModel


class WeatherSnapshot(BaseModel):
    condition: str | None = None
    temp_c: float | None = None
    wind_kph: float | None = None
    visibility_km: float | None = None
    source_timestamp: str | None = None
    source: str = "openweather"
    cache_hit: bool = False
    error: str | None = None
    rate_limited: bool = False


class WeatherStore:
    """OpenWeather-backed current/historical weather snapshots with memory caching."""

    _cache: dict[str, WeatherSnapshot] = {}

    async def get_snapshot(
        self,
        lat: float,
        lon: float,
        observed_at: datetime | None,
        api_key: str,
    ) -> WeatherSnapshot:
        target = observed_at.astimezone(timezone.utc) if observed_at else datetime.now(timezone.utc)
        cache_key = self._cache_key(lat, lon, target)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached.model_copy(update={"cache_hit": True})

        if not api_key.strip():
            return WeatherSnapshot(error="OpenWeather API key required.")

        if observed_at is None:
            snapshot = await self._fetch_current(lat, lon, api_key)
        else:
            snapshot = await self._fetch_historical(lat, lon, target, api_key)

        if snapshot.error is None:
            self._cache[cache_key] = snapshot
        return snapshot

    async def _fetch_current(self, lat: float, lon: float, api_key: str) -> WeatherSnapshot:
        params = {"lat": lat, "lon": lon, "appid": api_key, "units": "metric"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get("https://api.openweathermap.org/data/2.5/weather", params=params)
            if resp.status_code == 429:
                return WeatherSnapshot(error="OpenWeather rate limit exceeded.", rate_limited=True)
            if resp.status_code == 401:
                return WeatherSnapshot(error="Invalid OpenWeather API key.")
            resp.raise_for_status()
            return self._parse_current(resp.json())
        except httpx.RequestError as exc:
            return WeatherSnapshot(error=f"Weather provider request failed: {exc}")
        except Exception as exc:
            return WeatherSnapshot(error=f"Weather provider error: {exc}")

    async def _fetch_historical(self, lat: float, lon: float, target: datetime, api_key: str) -> WeatherSnapshot:
        params = {
            "lat": lat,
            "lon": lon,
            "dt": int(target.timestamp()),
            "appid": api_key,
            "units": "metric",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.openweathermap.org/data/3.0/onecall/timemachine",
                    params=params,
                )
            if resp.status_code == 429:
                return WeatherSnapshot(error="OpenWeather rate limit exceeded.", rate_limited=True)
            if resp.status_code == 401:
                return WeatherSnapshot(error="Invalid OpenWeather API key.")
            resp.raise_for_status()
            return self._parse_historical(resp.json())
        except httpx.RequestError as exc:
            return WeatherSnapshot(error=f"Weather provider request failed: {exc}")
        except Exception as exc:
            return WeatherSnapshot(error=f"Weather provider error: {exc}")

    def _parse_current(self, payload: dict) -> WeatherSnapshot:
        weather = payload.get("weather") or [{}]
        main = payload.get("main") or {}
        wind = payload.get("wind") or {}
        timestamp = self._timestamp_to_iso(payload.get("dt"))
        return WeatherSnapshot(
            condition=self._condition_from_weather(weather),
            temp_c=self._to_float(main.get("temp")),
            wind_kph=self._wind_to_kph(wind.get("speed")),
            visibility_km=self._visibility_to_km(payload.get("visibility")),
            source_timestamp=timestamp,
        )

    def _parse_historical(self, payload: dict) -> WeatherSnapshot:
        rows = payload.get("data") or []
        first = rows[0] if rows else {}
        weather = first.get("weather") or [{}]
        timestamp = self._timestamp_to_iso(first.get("dt"))
        return WeatherSnapshot(
            condition=self._condition_from_weather(weather),
            temp_c=self._to_float(first.get("temp")),
            wind_kph=self._wind_to_kph(first.get("wind_speed")),
            visibility_km=self._visibility_to_km(first.get("visibility")),
            source_timestamp=timestamp,
        )

    @staticmethod
    def _cache_key(lat: float, lon: float, target: datetime) -> str:
        bucket = target.replace(minute=0, second=0, microsecond=0).isoformat()
        return f"{round(lat, 2):.2f}:{round(lon, 2):.2f}:{bucket}"

    @staticmethod
    def _condition_from_weather(weather: list[dict]) -> str | None:
        first = weather[0] if weather else {}
        if not isinstance(first, dict):
            return None
        text = first.get("description") or first.get("main")
        return text.strip() if isinstance(text, str) and text.strip() else None

    @staticmethod
    def _to_float(value: object) -> float | None:
        try:
            return round(float(value), 2)
        except Exception:
            return None

    @classmethod
    def _wind_to_kph(cls, value: object) -> float | None:
        raw = cls._to_float(value)
        return round(raw * 3.6, 2) if raw is not None else None

    @classmethod
    def _visibility_to_km(cls, value: object) -> float | None:
        raw = cls._to_float(value)
        return round(raw / 1000.0, 2) if raw is not None else None

    @staticmethod
    def _timestamp_to_iso(value: object) -> str | None:
        try:
            return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()
        except Exception:
            return None
