import httpx

from ogi.models import Entity, EntityType, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig

INTERESTING_HEADERS = [
    "Server",
    "X-Powered-By",
    "Content-Type",
    "X-Frame-Options",
    "Strict-Transport-Security",
    "Content-Security-Policy",
]


class URLToHeaders(BaseTransform):
    name = "url_to_headers"
    display_name = "URL to HTTP Headers"
    description = "Performs a HEAD request and extracts interesting HTTP headers from a URL"
    input_types = [EntityType.URL]
    output_types = [EntityType.URL]
    category = "Web"

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        url = entity.value
        entities: list[Entity] = []
        messages: list[str] = []

        header_properties: dict[str, str | int | float | bool | None] = {}

        try:
            async with httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True,
                verify=False,
            ) as client:
                response = await client.head(url)

            header_properties["http_status_code"] = response.status_code
            messages.append(f"HTTP {response.status_code}")

            for header_name in INTERESTING_HEADERS:
                value = response.headers.get(header_name)
                if value:
                    prop_key = f"header_{header_name.lower().replace('-', '_')}"
                    header_properties[prop_key] = value
                    messages.append(f"{header_name}: {value}")

            if not any(
                response.headers.get(h) for h in INTERESTING_HEADERS
            ):
                messages.append("No interesting headers found")

            enriched_entity = Entity(
                type=entity.type,
                value=entity.value,
                properties={**entity.properties, **header_properties},
                source=self.name,
            )
            entities.append(enriched_entity)

        except httpx.TimeoutException:
            messages.append(f"Timeout connecting to {url}")
        except httpx.ConnectError:
            messages.append(f"Connection error for {url}")
        except httpx.TooManyRedirects:
            messages.append(f"Too many redirects for {url}")
        except httpx.HTTPError as e:
            messages.append(f"HTTP error for {url}: {e}")
        except Exception as e:
            messages.append(f"Error fetching headers from {url}: {e}")

        return TransformResult(entities=entities, edges=[], messages=messages)
