from __future__ import annotations

import time
from math import asin, cos, radians, sin, sqrt

import httpx
from pydantic import BaseModel, Field


class NearbyFacility(BaseModel):
    fac_id: int
    name: str
    city: str = ""
    country: str = ""
    latitude: float
    longitude: float
    distance_km: float


class NearbyNetworkPresence(BaseModel):
    fac_id: int
    facility_name: str
    distance_km: float
    asn: int
    network_name: str | None = None


class NearbyNetworkResult(BaseModel):
    presences: list[NearbyNetworkPresence] = Field(default_factory=list)
    source: str = "peeringdb"
    error: str | None = None


class NearbyNetworkStore:
    """Nearby network infrastructure lookup using PeeringDB facility/network presence data."""

    BASE_URL = "https://www.peeringdb.com/api"
    MAX_RADIUS_KM = 100
    MAX_FACILITY_EXPANSIONS = 10
    MAX_ASN_DETAILS = 30
    CACHE_TTL_SECONDS = 1800
    RATE_LIMIT_COOLDOWN_SECONDS = 120
    _facility_cache: dict[str, tuple[float, list[NearbyFacility]]] = {}
    _netfac_cache: dict[int, tuple[float, list[NearbyNetworkPresence]]] = {}
    _network_name_cache: dict[int, tuple[float, str]] = {}
    _cooldown_until: float = 0.0

    async def get_nearby_networks(
        self,
        *,
        lat: float,
        lon: float,
        radius_km: int,
        city: str | None = None,
        country: str | None = None,
        api_key: str = "",
        timeout_seconds: float = 8.0,
    ) -> NearbyNetworkResult:
        radius = max(1, min(int(radius_km), self.MAX_RADIUS_KM))
        retry_after = self._retry_after_seconds()
        if retry_after > 0:
            return NearbyNetworkResult(
                error=(
                    "Nearby ASN provider temporarily rate-limited. "
                    f"Retry in about {retry_after}s."
                )
            )
        try:
            headers = {}
            if api_key.strip():
                headers["Authorization"] = f"api-key {api_key.strip()}"
            async with httpx.AsyncClient(timeout=timeout_seconds, headers=headers or None) as client:
                facilities = await self._fetch_facilities(client, city=city, country=country)
                facilities = self.with_distances(facilities, lat=lat, lon=lon)
                nearby_facilities = [
                    facility
                    for facility in facilities
                    if facility.distance_km <= radius
                ]
                nearby_facilities.sort(key=lambda facility: facility.distance_km)
                nearby_facilities = nearby_facilities[: self.MAX_FACILITY_EXPANSIONS]
                if not nearby_facilities:
                    return NearbyNetworkResult(presences=[])

                presences: list[NearbyNetworkPresence] = []
                for facility in nearby_facilities:
                    rows = await self._fetch_netfac(client, facility)
                    presences.extend(rows)

                asns = sorted({row.asn for row in presences})[: self.MAX_ASN_DETAILS]
                names_by_asn = await self._fetch_network_names(client, asns)

                enriched = [
                    row.model_copy(update={"network_name": names_by_asn.get(row.asn)})
                    for row in presences
                ]
                return NearbyNetworkResult(presences=enriched)
        except httpx.RequestError as exc:
            return NearbyNetworkResult(error=f"Nearby ASN provider request failed: {exc}")
        except Exception as exc:
            return NearbyNetworkResult(error=f"Nearby ASN provider error: {exc}")

    async def _fetch_facilities(
        self,
        client: httpx.AsyncClient,
        *,
        city: str | None,
        country: str | None,
    ) -> list[NearbyFacility]:
        cache_key = f"{(city or '').strip().lower()}|{(country or '').strip().lower()}"
        cached = self._cache_get(self._facility_cache, cache_key)
        if cached is not None:
            return cached

        params: dict[str, str] = {}
        if city:
            params["city"] = city
        if country:
            params["country"] = country

        resp = await client.get(f"{self.BASE_URL}/fac", params=params)
        if resp.status_code == 429:
            self._start_cooldown()
            raise httpx.RequestError("PeeringDB rate limit exceeded", request=resp.request)
        resp.raise_for_status()

        payload = resp.json()
        data = payload.get("data", []) if isinstance(payload, dict) else []
        facilities: list[NearbyFacility] = []
        for row in data:
            lat = self._to_float(row.get("latitude"))
            lon = self._to_float(row.get("longitude"))
            if lat is None or lon is None:
                continue
            facilities.append(
                NearbyFacility(
                    fac_id=int(row.get("id")),
                    name=str(row.get("name") or f"Facility {row.get('id')}"),
                    city=str(row.get("city") or ""),
                    country=str(row.get("country") or ""),
                    latitude=lat,
                    longitude=lon,
                    distance_km=0.0,
                )
            )
        self._cache_set(self._facility_cache, cache_key, facilities)
        return facilities

    async def _fetch_netfac(
        self,
        client: httpx.AsyncClient,
        facility: NearbyFacility,
    ) -> list[NearbyNetworkPresence]:
        cached = self._cache_get(self._netfac_cache, facility.fac_id)
        if cached is not None:
            return [
                row.model_copy(update={"distance_km": facility.distance_km, "facility_name": facility.name})
                for row in cached
            ]

        resp = await client.get(f"{self.BASE_URL}/netfac", params={"fac_id": facility.fac_id})
        if resp.status_code == 429:
            self._start_cooldown()
            raise httpx.RequestError("PeeringDB rate limit exceeded", request=resp.request)
        resp.raise_for_status()

        payload = resp.json()
        data = payload.get("data", []) if isinstance(payload, dict) else []
        rows: list[NearbyNetworkPresence] = []
        for row in data:
            asn = row.get("local_asn")
            if asn is None:
                continue
            rows.append(
                NearbyNetworkPresence(
                    fac_id=facility.fac_id,
                    facility_name=facility.name,
                    distance_km=facility.distance_km,
                    asn=int(asn),
                )
            )
        self._cache_set(
            self._netfac_cache,
            facility.fac_id,
            [
                row.model_copy(update={"distance_km": 0.0})
                for row in rows
            ],
        )
        return rows

    async def _fetch_network_names(
        self,
        client: httpx.AsyncClient,
        asns: list[int],
    ) -> dict[int, str]:
        names: dict[int, str] = {}
        for asn in asns:
            cached = self._cache_get(self._network_name_cache, asn)
            if cached is not None:
                names[asn] = cached
                continue
            resp = await client.get(f"{self.BASE_URL}/net", params={"asn": asn})
            if resp.status_code == 429:
                self._start_cooldown()
                break
            if resp.status_code >= 400:
                continue
            payload = resp.json()
            data = payload.get("data", []) if isinstance(payload, dict) else []
            if not data:
                continue
            row = data[0]
            name = str(row.get("name") or "").strip()
            if name:
                names[asn] = name
                self._cache_set(self._network_name_cache, asn, name)
        return names

    @staticmethod
    def with_distances(
        facilities: list[NearbyFacility],
        *,
        lat: float,
        lon: float,
    ) -> list[NearbyFacility]:
        return [
            facility.model_copy(
                update={
                    "distance_km": NearbyNetworkStore.haversine_km(
                        lat,
                        lon,
                        facility.latitude,
                        facility.longitude,
                    )
                }
            )
            for facility in facilities
        ]

    @staticmethod
    def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        r = 6371.0
        d_lat = radians(lat2 - lat1)
        d_lon = radians(lon2 - lon1)
        a = (
            sin(d_lat / 2) ** 2
            + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
        )
        c = 2 * asin(sqrt(a))
        return round(r * c, 2)

    @staticmethod
    def _to_float(value: object) -> float | None:
        try:
            return float(value)
        except Exception:
            return None

    @classmethod
    def _cache_get(cls, cache: dict, key: object):
        row = cache.get(key)
        if row is None:
            return None
        expires_at, value = row
        if expires_at <= time.time():
            cache.pop(key, None)
            return None
        return value

    @classmethod
    def _cache_set(cls, cache: dict, key: object, value: object) -> None:
        cache[key] = (time.time() + cls.CACHE_TTL_SECONDS, value)

    @classmethod
    def _start_cooldown(cls) -> None:
        cls._cooldown_until = max(cls._cooldown_until, time.time() + cls.RATE_LIMIT_COOLDOWN_SECONDS)

    @classmethod
    def _retry_after_seconds(cls) -> int:
        remaining = int(round(cls._cooldown_until - time.time()))
        return max(0, remaining)
