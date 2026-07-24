from __future__ import annotations

from ogi.db.database import get_session
from ogi.models import Entity, EntityType, TransformResult
from ogi.store.location_search_store import LocationSearchStore
from ogi.transforms.base import BaseTransform, TransformConfig


class LocationToReverseGeocode(BaseTransform):
    name = "location_to_reverse_geocode"
    display_name = "Location to Reverse Geocode"
    description = "Converts coordinates into structured address components."
    input_types = [EntityType.LOCATION]
    output_types = [EntityType.LOCATION]
    category = "Location"
    long_description = (
        "Reads the lat and lon properties of a Location entity and asks the location "
        "search store for the matching address. The store serves an in-memory "
        "reverse-geocode cache keyed on the coordinates rounded to four decimal places and "
        "otherwise calls the Nominatim reverse API on OpenStreetMap. Emits a single "
        "Location entity that keeps the original value but adds the resolved address "
        "fields: location_label, geo_confidence, road, city, county, region, state, "
        "country, postcode, and address_hierarchy holding the geocoder's full raw address "
        "breakdown. No edges are created; the enriched entity supersedes the sparse one. "
        "Run messages report whether the cache or a live upstream request answered and "
        "print a short address summary. Missing or unparseable coordinates stop the "
        "transform, as does an active rate-limit cooldown."
    )
    when_to_use = (
        "Use this when the investigation gives you coordinates, from photo EXIF data, a "
        "GPS log, a device ping or IP to Geolocation, and you need the human-readable "
        "address, administrative area or postcode behind them. Run Location to Geocode "
        "first if the entity has no coordinates yet, and follow with Location to Timezone "
        "or Location to Nearby ASNs to build context around the resolved place."
    )
    limitations = (
        "Nominatim returns the nearest addressable feature, so coordinates in open "
        "country, at sea or in sparsely mapped regions can resolve to a road or settlement "
        "some distance away, and the depth of address detail follows local OpenStreetMap "
        "coverage. The cache key rounds to four decimals, roughly eleven metres, so points "
        "inside that cell share one answer. Nominatim's usage policy allows about one "
        "request per second and the store enters a sixty-second cooldown after an upstream "
        "rate-limit response, during which only a retry message is returned."
    )
    example_use_cases = [
        "Resolve photo EXIF coordinates to a street address and neighbourhood",
        "Convert a GPS track point into an administrative area for a jurisdiction question",
        "Attach postcode and country fields to coordinates from IP to Geolocation",
    ]

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        properties = dict(entity.properties or {})
        lat = self._to_float(properties.get("lat"))
        lon = self._to_float(properties.get("lon"))
        if lat is None or lon is None:
            return TransformResult(messages=["Reverse geocoding skipped: missing valid coordinates."])

        resolution = None
        async for session in get_session():
            resolution = await LocationSearchStore(session).reverse_geocode(lat, lon)
            break

        if resolution is None:
            return TransformResult(messages=["Reverse geocoding failed."])
        if resolution.rate_limited:
            retry = resolution.retry_after_seconds or 60
            return TransformResult(
                messages=[
                    f"Reverse geocoding rate-limited. Retry in about {retry}s.",
                    "No upstream request was completed.",
                ]
            )

        if resolution.display_name:
            properties["location_label"] = resolution.display_name
        if resolution.confidence is not None:
            properties["geo_confidence"] = resolution.confidence
        if resolution.road:
            properties["road"] = resolution.road
        if resolution.city:
            properties["city"] = resolution.city
        if resolution.county:
            properties["county"] = resolution.county
        if resolution.region:
            properties["region"] = resolution.region
            properties["state"] = resolution.region
        if resolution.country:
            properties["country"] = resolution.country
        if resolution.postcode:
            properties["postcode"] = resolution.postcode
        if resolution.address_hierarchy:
            properties["address_hierarchy"] = resolution.address_hierarchy

        messages = [
            (
                f"Reverse geocoded ({lat:.5f}, {lon:.5f}) to "
                f"{resolution.display_name}."
            )
            if resolution.display_name
            else f"Reverse geocoded ({lat:.5f}, {lon:.5f})."
        ]
        messages.append("Used reverse-geocode cache." if resolution.cache_hit else "Used upstream reverse geocoder.")
        if resolution.road or resolution.city or resolution.country:
            summary = ", ".join(
                part
                for part in [resolution.road, resolution.city, resolution.region, resolution.country]
                if part
            )
            if summary:
                messages.append(f"Address summary: {summary}.")

        return TransformResult(
            entities=[
                Entity(
                    type=EntityType.LOCATION,
                    value=entity.value,
                    properties=properties,
                    project_id=entity.project_id,
                    source=self.name,
                )
            ],
            messages=messages,
        )

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
