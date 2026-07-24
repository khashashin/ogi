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
    long_description = (
        "Takes the free-text value of a Location entity and resolves it to canonical "
        "coordinates through the location search store, which checks a persistent geocode "
        "cache first and otherwise queries the Nominatim search API on OpenStreetMap. "
        "Emits a new Location entity whose value is the geocoder's full display name and "
        "whose properties carry lat, lon, location_label, geo_confidence, and whichever of "
        "country, region, state, city and postcode the address record contains. When the "
        "canonical name differs from the text you supplied, a 'normalized to' edge links "
        "the original entity to the normalized one. Run messages state whether the answer "
        "came from the cache or from a live upstream request. While the shared upstream "
        "throttle or a rate-limit cooldown is in effect the transform returns a retry "
        "message and creates nothing."
    )
    when_to_use = (
        "Use this first whenever a Location entity holds an address, place name or other "
        "free text rather than coordinates, because the other Location transforms need lat "
        "and lon properties to work. Once coordinates exist, pivot to Location to Reverse "
        "Geocode for full address components, or to Location to Timezone, Location to Sun "
        "Times, Location to Weather Snapshot and Location to Nearby ASNs."
    )
    limitations = (
        "Only the single best Nominatim match is kept, so vague or duplicated place names, "
        "such as a common street name or a city name reused in several countries, can "
        "resolve to the wrong place. The geo_confidence value is a heuristic derived from "
        "the geocoder's importance and place rank, not a measured accuracy. Nominatim's "
        "usage policy allows roughly one request per second, so bulk runs return "
        "rate-limit messages instead of results. Coordinates describe the centroid of the "
        "matched feature, which for a city or region can be kilometres from the point you "
        "meant."
    )
    example_use_cases = [
        "Turn a street address from a witness statement into coordinates for enrichment",
        "Normalize location strings gathered from several sources so they can be compared",
        "Establish coordinates on a location before running weather or sun-time checks",
    ]

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
