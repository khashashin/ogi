import httpx

from ogi.models import Entity, EntityType, Edge, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig


class DomainToURLs(BaseTransform):
    name = "domain_to_urls"
    display_name = "Domain to URLs (robots.txt)"
    description = "Fetches robots.txt and extracts URLs from Sitemap and Disallow directives"
    input_types = [EntityType.DOMAIN]
    output_types = [EntityType.URL]
    category = "Web"

    async def run(self, entity: Entity, _config: TransformConfig) -> TransformResult:
        domain = entity.value
        entities: list[Entity] = []
        edges: list[Edge] = []
        messages: list[str] = []
        max_urls = self.get_effective_setting_max("max_urls", 50)

        robots_url = f"https://{domain}/robots.txt"

        try:
            async with httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True,
            ) as client:
                response = await client.get(robots_url)

            if response.status_code != 200:
                messages.append(
                    f"robots.txt returned HTTP {response.status_code}"
                )
                return TransformResult(
                    entities=entities, edges=edges, messages=messages
                )

            content = response.text
            found_paths: list[str] = []

            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                if line.lower().startswith("sitemap:"):
                    sitemap_url = line[len("sitemap:"):].strip()
                    if sitemap_url and sitemap_url not in found_paths:
                        found_paths.append(sitemap_url)

                elif line.lower().startswith("disallow:"):
                    path = line[len("disallow:"):].strip()
                    if path and path != "/":
                        full_url = f"https://{domain}{path}"
                        if full_url not in found_paths:
                            found_paths.append(full_url)

            if not found_paths:
                messages.append("No paths found in robots.txt")
                return TransformResult(
                    entities=entities, edges=edges, messages=messages
                )

            total_found = len(found_paths)
            truncated = max_urls is not None and total_found > int(max_urls)
            found_paths = found_paths[: int(max_urls) if max_urls is not None else None]

            for url_value in found_paths:
                url_entity = Entity(
                    type=EntityType.URL,
                    value=url_value,
                    properties={"source_file": "robots.txt"},
                    source=self.name,
                )
                entities.append(url_entity)
                edges.append(
                    Edge(
                        source_id=entity.id,
                        target_id=url_entity.id,
                        label="hosts",
                        source_transform=self.name,
                    )
                )

            messages.append(f"Found {total_found} URLs in robots.txt")
            if truncated:
                messages.append(f"Results limited to {int(max_urls)} URLs")

        except httpx.TimeoutException:
            messages.append(f"Timeout fetching robots.txt from {domain}")
        except httpx.ConnectError:
            messages.append(f"Connection error for {domain}")
        except httpx.TooManyRedirects:
            messages.append(f"Too many redirects fetching robots.txt from {domain}")
        except httpx.HTTPError as e:
            messages.append(f"HTTP error fetching robots.txt: {e}")
        except Exception as e:
            messages.append(f"Error fetching robots.txt from {domain}: {e}")

        return TransformResult(entities=entities, edges=edges, messages=messages)
