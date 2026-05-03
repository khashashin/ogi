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
