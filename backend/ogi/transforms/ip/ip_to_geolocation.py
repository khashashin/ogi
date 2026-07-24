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
    long_description = (
        "Queries the free ip-api.com JSON endpoint over HTTP for the supplied address and "
        "creates a single Location entity from the response, linked to the IP with a "
        "'located in' edge. The location value is assembled from city, region and country, "
        "falling back to the IP itself when none of those are returned, and the entity "
        "carries country, city, region, lat, lon, isp and org as properties. No API key or "
        "account is needed. If ip-api.com reports a failed status the transform returns only "
        "a message and no entities."
    )
    when_to_use = (
        "Use it after resolving a domain to its addresses, or on any IP already in the graph, "
        "when you need a rough physical placement and the name of the network operator behind "
        "it. The isp and org properties usually name the hosting provider, which pairs well "
        "with IP to ASN for confirming who announces the address."
    )
    limitations = (
        "IP geolocation is approximate. Results frequently point at the ISP's or hosting "
        "provider's registered address rather than where the target actually is, and "
        "city-level precision is unreliable outside large consumer networks. VPNs, proxies, "
        "Tor and carrier NAT place the result wherever the exit node sits. Only one Location "
        "entity is produced per lookup, the free endpoint is rate limited per requesting host, "
        "and the query is sent over plain HTTP so it can be observed or altered in transit."
    )
    example_use_cases = [
        "Add a country and city estimate to an IP found during infrastructure mapping",
        "Identify the hosting provider or ISP behind a suspicious address",
        "Compare where a service claims to operate with where its servers resolve",
    ]

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
