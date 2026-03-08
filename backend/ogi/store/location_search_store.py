from __future__ import annotations

import time
from datetime import datetime, timezone

import httpx
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from ogi.models import GeocodeCache, LocationSuggestResponse, LocationSuggestion


class LocationGeocodeResult(BaseModel):
    query: str
    lat: float | None = None
    lon: float | None = None
    display_name: str = ""
    confidence: float | None = None
    source: str = "cache"
    country: str | None = None
    region: str | None = None
    city: str | None = None
    postcode: str | None = None
    rate_limited: bool = False
    retry_after_seconds: int | None = None
    cache_hit: bool = False
    road: str | None = None
    county: str | None = None
    address_hierarchy: dict[str, str] = {}


class LocationSearchStore:
    """Cache-first location autocomplete backed by Nominatim with gentle upstream throttling."""

    _next_upstream_at: float = 0.0
    _cooldown_until: float = 0.0
    _memory_cache: dict[str, tuple[float, list[LocationSuggestion]]] = {}
    _memory_ttl_seconds: int = 300
    _reverse_memory_cache: dict[str, tuple[float, LocationGeocodeResult]] = {}

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def normalize(self, query: str) -> LocationGeocodeResult:
        q = query.strip()
        normalized = q.lower()
        if not q:
            return LocationGeocodeResult(query=q, source="cache")

        cached = await self._get_cache_exact(normalized)
        if cached is not None:
            return LocationGeocodeResult(
                query=q,
                lat=cached.lat,
                lon=cached.lon,
                display_name=cached.display_name or q,
                confidence=cached.confidence,
                source="cache",
                cache_hit=True,
            )

        now = time.time()
        if now < self._cooldown_until:
            retry = max(1, int(self._cooldown_until - now))
            return LocationGeocodeResult(
                query=q,
                source="rate-limit",
                rate_limited=True,
                retry_after_seconds=retry,
            )

        if now < self._next_upstream_at:
            retry = max(1, int(self._next_upstream_at - now))
            return LocationGeocodeResult(
                query=q,
                source="throttle",
                rate_limited=True,
                retry_after_seconds=retry,
            )

        upstream = await self._fetch_nominatim_detail(q)
        if upstream is None:
            self._cooldown_until = time.time() + 60
            return LocationGeocodeResult(
                query=q,
                source="rate-limit",
                rate_limited=True,
                retry_after_seconds=60,
            )

        self._next_upstream_at = time.time() + 1.0
        if upstream.lat is None or upstream.lon is None:
            return upstream

        await self._upsert_cache(
            normalized,
            LocationSuggestion(
                label=upstream.display_name or q,
                display_name=upstream.display_name or q,
                lat=upstream.lat,
                lon=upstream.lon,
                source=upstream.source,
            ),
            confidence=upstream.confidence or 0.6,
        )
        display_key = (upstream.display_name or "").strip().lower()
        if display_key and display_key != normalized:
            await self._upsert_cache(
                display_key,
                LocationSuggestion(
                    label=upstream.display_name,
                    display_name=upstream.display_name,
                    lat=upstream.lat,
                    lon=upstream.lon,
                    source=upstream.source,
                ),
                confidence=upstream.confidence or 0.6,
            )
        return upstream

    async def suggest(self, query: str, limit: int = 5) -> LocationSuggestResponse:
        q = query.strip()
        if len(q) < 3:
            return LocationSuggestResponse(query=q, suggestions=[], source="cache")

        normalized = q.lower()

        mem_hit = self._memory_cache.get(normalized)
        now = time.time()
        if mem_hit and (now - mem_hit[0]) < self._memory_ttl_seconds:
            return LocationSuggestResponse(query=q, suggestions=mem_hit[1][:limit], source="memory")

        cache_suggestions = await self._cache_prefix_lookup(normalized, limit)
        if cache_suggestions:
            self._memory_cache[normalized] = (now, cache_suggestions)
            return LocationSuggestResponse(query=q, suggestions=cache_suggestions, source="cache")

        if now < self._cooldown_until:
            retry = max(1, int(self._cooldown_until - now))
            return LocationSuggestResponse(
                query=q,
                suggestions=[],
                source="rate-limit",
                rate_limited=True,
                retry_after_seconds=retry,
            )

        if now < self._next_upstream_at:
            retry = max(1, int(self._next_upstream_at - now))
            return LocationSuggestResponse(
                query=q,
                suggestions=[],
                source="throttle",
                rate_limited=True,
                retry_after_seconds=retry,
            )

        upstream = await self._fetch_nominatim(q, limit)
        if upstream is None:
            # Upstream explicitly rate-limited us.
            self._cooldown_until = time.time() + 60
            return LocationSuggestResponse(
                query=q,
                suggestions=[],
                source="rate-limit",
                rate_limited=True,
                retry_after_seconds=60,
            )

        self._next_upstream_at = time.time() + 1.0
        suggestions = [s for s in upstream if s.display_name]
        self._memory_cache[normalized] = (time.time(), suggestions)

        for item in suggestions:
            await self._upsert_cache(item.display_name.lower(), item)

        return LocationSuggestResponse(query=q, suggestions=suggestions[:limit], source="nominatim")

    async def reverse_geocode(self, lat: float, lon: float) -> LocationGeocodeResult:
        rounded_lat = round(lat, 4)
        rounded_lon = round(lon, 4)
        cache_key = self._reverse_cache_key(rounded_lat, rounded_lon)
        now = time.time()

        mem_hit = self._reverse_memory_cache.get(cache_key)
        if mem_hit and (now - mem_hit[0]) < self._memory_ttl_seconds:
            return mem_hit[1].model_copy(update={"cache_hit": True, "source": "cache"})

        if now < self._cooldown_until:
            retry = max(1, int(self._cooldown_until - now))
            return LocationGeocodeResult(
                query=cache_key,
                lat=lat,
                lon=lon,
                source="rate-limit",
                rate_limited=True,
                retry_after_seconds=retry,
            )

        if now < self._next_upstream_at:
            retry = max(1, int(self._next_upstream_at - now))
            return LocationGeocodeResult(
                query=cache_key,
                lat=lat,
                lon=lon,
                source="throttle",
                rate_limited=True,
                retry_after_seconds=retry,
            )

        upstream = await self._fetch_nominatim_reverse(lat, lon)
        if upstream is None:
            self._cooldown_until = time.time() + 60
            return LocationGeocodeResult(
                query=cache_key,
                lat=lat,
                lon=lon,
                source="rate-limit",
                rate_limited=True,
                retry_after_seconds=60,
            )

        self._next_upstream_at = time.time() + 1.0
        if upstream.lat is None or upstream.lon is None:
            upstream.lat = lat
            upstream.lon = lon

        self._reverse_memory_cache[cache_key] = (time.time(), upstream)
        return upstream

    async def _get_cache_exact(self, normalized_query: str) -> GeocodeCache | None:
        stmt = select(GeocodeCache).where(GeocodeCache.query == normalized_query)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _cache_prefix_lookup(self, normalized_query: str, limit: int) -> list[LocationSuggestion]:
        stmt = (
            select(GeocodeCache)
            .where(GeocodeCache.query.like(f"{normalized_query}%"))
            .order_by(GeocodeCache.updated_at.desc())
            .limit(limit)
        )
        rows = list((await self.session.execute(stmt)).scalars().all())
        return [
            LocationSuggestion(
                label=row.display_name or row.query,
                display_name=row.display_name or row.query,
                lat=row.lat,
                lon=row.lon,
                source=row.source,
            )
            for row in rows
        ]

    async def _upsert_cache(self, query: str, suggestion: LocationSuggestion, confidence: float = 0.6) -> None:
        stmt = select(GeocodeCache).where(GeocodeCache.query == query)
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if existing:
            existing.lat = suggestion.lat
            existing.lon = suggestion.lon
            existing.display_name = suggestion.display_name
            existing.source = suggestion.source
            existing.confidence = confidence
            existing.updated_at = now
            self.session.add(existing)
        else:
            self.session.add(
                GeocodeCache(
                    query=query,
                    lat=suggestion.lat,
                    lon=suggestion.lon,
                    display_name=suggestion.display_name,
                    confidence=confidence,
                    source=suggestion.source,
                )
            )
        await self.session.commit()

    async def _fetch_nominatim_detail(self, query: str) -> LocationGeocodeResult | None:
        params = {"q": query, "format": "jsonv2", "limit": "1", "addressdetails": "1"}
        headers = {"User-Agent": "OGI-LocationGeocoder/1.0"}
        try:
            async with httpx.AsyncClient(timeout=6) as client:
                resp = await client.get("https://nominatim.openstreetmap.org/search", params=params, headers=headers)
            if resp.status_code == 429:
                return None
            resp.raise_for_status()
            payload = resp.json()
        except Exception:
            return LocationGeocodeResult(query=query, source="nominatim")

        if not payload:
            return LocationGeocodeResult(query=query, source="nominatim")

        return self._parse_nominatim_result(query, payload[0])

    async def _fetch_nominatim(self, query: str, limit: int) -> list[LocationSuggestion] | None:
        params = {"q": query, "format": "jsonv2", "limit": str(limit), "addressdetails": "0"}
        headers = {"User-Agent": "OGI-LocationAutocomplete/1.0"}
        try:
            async with httpx.AsyncClient(timeout=6) as client:
                resp = await client.get("https://nominatim.openstreetmap.org/search", params=params, headers=headers)
            if resp.status_code == 429:
                return None
            resp.raise_for_status()
            payload = resp.json()
        except Exception:
            return []

        suggestions: list[LocationSuggestion] = []
        for item in payload:
            try:
                display = str(item.get("display_name", "")).strip()
                lat = float(item.get("lat"))
                lon = float(item.get("lon"))
                if not display:
                    continue
                suggestions.append(
                    LocationSuggestion(
                        label=display,
                        display_name=display,
                        lat=lat,
                        lon=lon,
                        source="nominatim",
                    )
                )
            except Exception:
                continue
        return suggestions

    async def _fetch_nominatim_reverse(self, lat: float, lon: float) -> LocationGeocodeResult | None:
        params = {
            "lat": f"{lat:.6f}",
            "lon": f"{lon:.6f}",
            "format": "jsonv2",
            "addressdetails": "1",
        }
        headers = {"User-Agent": "OGI-LocationReverseGeocoder/1.0"}
        try:
            async with httpx.AsyncClient(timeout=6) as client:
                resp = await client.get("https://nominatim.openstreetmap.org/reverse", params=params, headers=headers)
            if resp.status_code == 429:
                return None
            resp.raise_for_status()
            payload = resp.json()
        except Exception:
            return LocationGeocodeResult(query=self._reverse_cache_key(lat, lon), lat=lat, lon=lon, source="nominatim")

        if not isinstance(payload, dict):
            return LocationGeocodeResult(query=self._reverse_cache_key(lat, lon), lat=lat, lon=lon, source="nominatim")

        return self._parse_nominatim_result(self._reverse_cache_key(lat, lon), payload)

    def _parse_nominatim_result(self, query: str, item: dict) -> LocationGeocodeResult:
        address = item.get("address")
        address = address if isinstance(address, dict) else {}

        display_name = str(item.get("display_name", "")).strip()
        lat = self._safe_float(item.get("lat"))
        lon = self._safe_float(item.get("lon"))
        country = self._clean_text(address.get("country"))
        region = (
            self._clean_text(address.get("state"))
            or self._clean_text(address.get("region"))
            or self._clean_text(address.get("county"))
        )
        city = (
            self._clean_text(address.get("city"))
            or self._clean_text(address.get("town"))
            or self._clean_text(address.get("village"))
            or self._clean_text(address.get("municipality"))
            or self._clean_text(address.get("hamlet"))
        )
        postcode = self._clean_text(address.get("postcode"))
        road = (
            self._clean_text(address.get("road"))
            or self._clean_text(address.get("pedestrian"))
            or self._clean_text(address.get("footway"))
            or self._clean_text(address.get("residential"))
            or self._clean_text(address.get("path"))
        )
        county = self._clean_text(address.get("county"))
        address_hierarchy = {
            key: cleaned
            for key, value in address.items()
            if (cleaned := self._clean_text(value)) is not None
        }

        return LocationGeocodeResult(
            query=query,
            lat=lat,
            lon=lon,
            display_name=display_name,
            confidence=self._confidence_from_nominatim(item, address),
            source="nominatim",
            country=country,
            region=region,
            city=city,
            postcode=postcode,
            road=road,
            county=county,
            address_hierarchy=address_hierarchy,
        )

    @staticmethod
    def _safe_float(value: object) -> float | None:
        try:
            return float(value)
        except Exception:
            return None

    @staticmethod
    def _clean_text(value: object) -> str | None:
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned:
                return cleaned
        return None

    def _confidence_from_nominatim(self, item: dict, address: dict) -> float:
        importance = self._safe_float(item.get("importance")) or 0.0
        place_rank = self._safe_float(item.get("place_rank")) or 0.0
        score = 0.45
        score += min(0.25, max(0.0, importance) * 0.25)
        score += min(0.15, max(0.0, place_rank) / 30.0 * 0.15)
        if address.get("country"):
            score += 0.08
        if any(address.get(key) for key in ("city", "town", "village", "municipality", "state", "region")):
            score += 0.07
        return round(min(score, 0.95), 2)

    @staticmethod
    def _reverse_cache_key(lat: float, lon: float) -> str:
        return f"rev:{round(lat, 4):.4f}:{round(lon, 4):.4f}"
