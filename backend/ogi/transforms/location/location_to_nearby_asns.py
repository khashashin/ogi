from __future__ import annotations

from datetime import datetime, timezone

from ogi.store.location_search_store import LocationSearchStore
from ogi.models import Entity, EntityType, Edge, TransformResult
from ogi.store.nearby_network_store import NearbyNetworkPresence, NearbyNetworkStore
from ogi.transforms.base import BaseTransform, TransformConfig, TransformSetting


class LocationToNearbyASNs(BaseTransform):
    name = "location_to_nearby_asns"
    display_name = "Location to Nearby ASNs"
    description = "Finds nearby ASN and network presence around a location using public peering facility data."
    input_types = [EntityType.LOCATION]
    output_types = [EntityType.AS_NUMBER, EntityType.NETWORK]
    category = "Location"
    settings = [
        TransformSetting(
            name="radius_km",
            display_name="Radius (km)",
            description="Search radius around the location in kilometers.",
            required=False,
            default="25",
            field_type="integer",
            min_value=1,
            max_value=float(NearbyNetworkStore.MAX_RADIUS_KM),
        ),
        TransformSetting(
            name="provider_timeout_seconds",
            display_name="Provider Timeout (s)",
            description="Timeout for nearby network provider requests.",
            required=False,
            default="8",
            field_type="number",
            min_value=1,
            max_value=20,
        ),
        TransformSetting(
            name="peeringdb_api_key",
            display_name="PeeringDB API Key",
            description="Optional API key for higher PeeringDB query limits.",
            required=False,
            field_type="secret",
        ),
        TransformSetting(
            name="target_datetime",
            display_name="Target Date/Time",
            description="Optional ISO-8601 reference time for analyst context. Nearby ASN data is current-state only.",
            required=False,
            field_type="string",
        ),
    ]

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        props = dict(entity.properties or {})
        lat = self._to_float(props.get("lat"))
        lon = self._to_float(props.get("lon"))
        messages: list[str] = []
        if lat is None or lon is None:
            return TransformResult(messages=["Nearby ASN lookup skipped: missing valid coordinates."])

        city = self._string_or_none(props.get("city"))
        country = self._string_or_none(props.get("country"))
        if city is None and country is None:
            geocoded = await self._resolve_admin_context(entity.value)
            if geocoded is not None:
                if geocoded.city:
                    city = geocoded.city
                    props["city"] = geocoded.city
                if geocoded.country:
                    country = geocoded.country
                    props["country"] = geocoded.country
                if geocoded.display_name:
                    props["location_label"] = geocoded.display_name
                if geocoded.confidence is not None:
                    props["geo_confidence"] = geocoded.confidence
                messages.append("Administrative context was resolved via geocoding before nearby ASN lookup.")

        if city is None and country is None:
            return TransformResult(
                messages=[
                    "Nearby ASN lookup skipped: city or country context is required.",
                    "Run geocoding first or provide a more specific location label.",
                ]
            )

        target_datetime_raw = config.settings.get("target_datetime", "")
        target_datetime = self._parse_datetime(target_datetime_raw)
        if target_datetime_raw.strip() and target_datetime is None:
            return TransformResult(messages=["Nearby ASN lookup skipped: invalid target_datetime. Use ISO-8601 format."])

        radius_km = self._parse_int(config.settings.get("radius_km"), default=25)
        radius_km = max(1, min(radius_km, NearbyNetworkStore.MAX_RADIUS_KM))
        timeout_seconds = self._parse_float(config.settings.get("provider_timeout_seconds"), default=8.0)
        timeout_seconds = max(1.0, min(timeout_seconds, 20.0))

        result = await NearbyNetworkStore().get_nearby_networks(
            lat=lat,
            lon=lon,
            radius_km=radius_km,
            city=city,
            country=country,
            api_key=config.settings.get("peeringdb_api_key", "").strip(),
            timeout_seconds=timeout_seconds,
        )
        if result.error:
            return TransformResult(messages=[result.error])
        if not result.presences:
            return TransformResult(messages=[f"No nearby network infrastructure found within {radius_km} km."])

        entities: list[Entity] = []
        edges: list[Edge] = []
        messages.append(
            f"Found {len(result.presences)} nearby network presences across {len({row.asn for row in result.presences})} ASNs within {radius_km} km."
        )
        if target_datetime is not None:
            messages.append(f"Reference timestamp noted: {target_datetime.isoformat()}. Nearby ASN data is current-state only.")

        by_asn: dict[int, list[NearbyNetworkPresence]] = {}
        for presence in result.presences:
            by_asn.setdefault(presence.asn, []).append(presence)

        sorted_asns = sorted(by_asn.items(), key=lambda item: min(row.distance_km for row in item[1]))
        for asn, presences in sorted_asns:
            nearest = min(presences, key=lambda row: row.distance_km)
            facility_names = sorted({row.facility_name for row in presences if row.facility_name})
            network_names = sorted({row.network_name.strip() for row in presences if row.network_name and row.network_name.strip()})

            as_entity = Entity(
                type=EntityType.AS_NUMBER,
                value=f"AS{asn}",
                properties={
                    "asn": asn,
                    "nearby_radius_km": radius_km,
                    "nearby_presence_count": len(presences),
                    "nearby_facility_count": len({row.fac_id for row in presences}),
                    "nearest_facility_name": nearest.facility_name,
                    "nearest_facility_distance_km": nearest.distance_km,
                    "nearby_facilities": facility_names,
                },
                project_id=entity.project_id,
                source=self.name,
            )
            entities.append(as_entity)
            edges.append(
                Edge(
                    source_id=entity.id,
                    target_id=as_entity.id,
                    label="nearby_network",
                    properties={
                        "asn": asn,
                        "nearest_facility_name": nearest.facility_name,
                        "nearest_facility_distance_km": nearest.distance_km,
                        "radius_km": radius_km,
                    },
                    source_transform=self.name,
                )
            )

            if network_names:
                network_value = network_names[0]
                network_entity = Entity(
                    type=EntityType.NETWORK,
                    value=network_value,
                    properties={
                        "asn": f"AS{asn}",
                        "nearby_radius_km": radius_km,
                        "nearest_facility_name": nearest.facility_name,
                        "nearest_facility_distance_km": nearest.distance_km,
                        "nearby_facilities": facility_names,
                    },
                    project_id=entity.project_id,
                    source=self.name,
                )
                entities.append(network_entity)
                edges.append(
                    Edge(
                        source_id=entity.id,
                        target_id=network_entity.id,
                        label="nearby_network",
                        properties={
                            "asn": asn,
                            "nearest_facility_name": nearest.facility_name,
                            "nearest_facility_distance_km": nearest.distance_km,
                            "radius_km": radius_km,
                        },
                        source_transform=self.name,
                    )
                )

            messages.append(
                f"AS{asn} near {nearest.facility_name} ({nearest.distance_km:.1f} km)."
            )

        return TransformResult(entities=entities, edges=edges, messages=messages)

    @staticmethod
    def _string_or_none(value: object) -> str | None:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return None

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
    def _parse_int(value: object, *, default: int) -> int:
        if isinstance(value, bool):
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError:
                return default
        return default

    @staticmethod
    def _parse_float(value: object, *, default: float) -> float:
        if isinstance(value, bool):
            return default
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.strip())
            except ValueError:
                return default
        return default

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

    @staticmethod
    async def _resolve_admin_context(query: str):
        stripped = query.strip()
        if not stripped:
            return None
        async for session in LocationToNearbyASNs._get_session():
            return await LocationSearchStore(session).normalize(stripped)
        return None

    @staticmethod
    def _get_session():
        from ogi.db.database import get_session

        return get_session()
