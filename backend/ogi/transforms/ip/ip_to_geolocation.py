import httpx

from ogi.models import Entity, EntityType, Edge, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig


class IPToGeolocation(BaseTransform):
    name = "ip_to_geolocation"
    display_name = "IP to Geolocation"
    description = "Looks up geographic location for an IP address using ip-api.com"
    input_types = [EntityType.IP_ADDRESS]
    output_types = [EntityType.LOCATION]
    category = "IP Intelligence"

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        ip = entity.value
        entities: list[Entity] = []
        edges: list[Edge] = []
        messages: list[str] = []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"http://ip-api.com/json/{ip}")
                response.raise_for_status()
                data = response.json()

            if data.get("status") == "fail":
                messages.append(f"Geolocation lookup failed: {data.get('message', 'Unknown error')}")
                return TransformResult(entities=entities, edges=edges, messages=messages)

            country = data.get("country", "")
            city = data.get("city", "")
            region = data.get("regionName", "")
            lat = data.get("lat")
            lon = data.get("lon")
            isp = data.get("isp", "")
            org = data.get("org", "")

            location_parts = [p for p in [city, region, country] if p]
            location_value = ", ".join(location_parts) if location_parts else ip

            location_entity = Entity(
                type=EntityType.LOCATION,
                value=location_value,
                properties={
                    "country": country,
                    "city": city,
                    "region": region,
                    "lat": lat,
                    "lon": lon,
                    "isp": isp,
                    "org": org,
                },
                source=self.name,
            )
            entities.append(location_entity)
            edges.append(Edge(
                source_id=entity.id,
                target_id=location_entity.id,
                label="located in",
                source_transform=self.name,
            ))
            messages.append(f"Location: {location_value}")

        except httpx.HTTPStatusError as e:
            messages.append(f"HTTP error during geolocation lookup: {e}")
        except httpx.RequestError as e:
            messages.append(f"Request error during geolocation lookup: {e}")
        except Exception as e:
            messages.append(f"Error during geolocation lookup: {e}")

        return TransformResult(entities=entities, edges=edges, messages=messages)
