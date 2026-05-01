from __future__ import annotations

from ogi.db.database import get_session
from ogi.models import Entity, EntityType, Edge, TransformResult
from ogi.store.location_search_store import LocationSearchStore
from ogi.transforms.base import BaseTransform, TransformConfig


class LocationToGeocode(BaseTransform):
    name = "location_to_geocode"
    display_name = "Location to Geocode"
    description = "Normalizes a free-text location into canonical coordinates and admin fields."
    input_types = [EntityType.LOCATION]
    output_types = [EntityType.LOCATION]
    category = "Location"

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        query = entity.value.strip()
        if not query:
            return TransformResult(messages=["Location value is empty."])

        resolution = None
        async for session in get_session():
            resolution = await LocationSearchStore(session).normalize(query)
            break

        if resolution is None:
            return TransformResult(messages=[f"Unable to geocode '{query}'."])

        if resolution.rate_limited:
            retry = resolution.retry_after_seconds or 60
            return TransformResult(
                messages=[
                    f"Geocoding rate-limited for '{query}'. Retry in about {retry}s.",
                    "No upstream request was completed.",
                ]
            )

        if resolution.lat is None or resolution.lon is None:
            return TransformResult(messages=[f"No geocode result found for '{query}'."])

        normalized_value = (resolution.display_name or query).strip() or query
        properties = {
            **(entity.properties or {}),
            "lat": resolution.lat,
            "lon": resolution.lon,
            "location_label": normalized_value,
            "geo_confidence": resolution.confidence,
        }
        if resolution.country:
            properties["country"] = resolution.country
        if resolution.region:
            properties["region"] = resolution.region
            properties["state"] = resolution.region
        if resolution.city:
            properties["city"] = resolution.city
        if resolution.postcode:
            properties["postcode"] = resolution.postcode

        output = Entity(
            type=EntityType.LOCATION,
            value=normalized_value,
            properties=properties,
            project_id=entity.project_id,
            source=self.name,
        )

        messages = [
            f"Geocoded '{query}' to '{normalized_value}' ({resolution.lat:.5f}, {resolution.lon:.5f}).",
            f"Confidence: {(resolution.confidence or 0.0):.2f}.",
            "Used cache." if resolution.cache_hit else "Used upstream geocoder.",
        ]

        edges: list[Edge] = []
        if normalized_value.lower() != query.lower():
            edges.append(
                Edge(
                    source_id=entity.id,
                    target_id=output.id,
                    label="normalized to",
                    source_transform=self.name,
                )
            )

        return TransformResult(entities=[output], edges=edges, messages=messages)
