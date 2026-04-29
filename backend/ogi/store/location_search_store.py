from __future__ import annotations

import time
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from ogi.models import GeocodeCache, LocationSuggestResponse, LocationSuggestion


class LocationSearchStore:
    """Cache-first location autocomplete backed by Nominatim with gentle upstream throttling."""

    _next_upstream_at: float = 0.0
    _cooldown_until: float = 0.0
    _memory_cache: dict[str, tuple[float, list[LocationSuggestion]]] = {}
    _memory_ttl_seconds: int = 300

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

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

    async def _upsert_cache(self, query: str, suggestion: LocationSuggestion) -> None:
        stmt = select(GeocodeCache).where(GeocodeCache.query == query)
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if existing:
            existing.lat = suggestion.lat
            existing.lon = suggestion.lon
            existing.display_name = suggestion.display_name
            existing.source = suggestion.source
            existing.updated_at = now
            self.session.add(existing)
        else:
            self.session.add(
                GeocodeCache(
                    query=query,
                    lat=suggestion.lat,
                    lon=suggestion.lon,
                    display_name=suggestion.display_name,
                    confidence=0.6,
                    source=suggestion.source,
                )
            )
        await self.session.commit()

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
