from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import httpx

from ogi.models import Edge, Entity, EntityType, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig

HREF_PATTERN = re.compile(
    r"""<a\s[^>]*href\s*=\s*(?:"([^"]+)"|'([^']+)'|([^\s>]+))""",
    re.IGNORECASE,
)
MAX_LINKS = 100


class URLToLinks(BaseTransform):
    name = "url_to_links"
    display_name = "URL to Outbound Links"
    description = "Fetches a page and extracts outbound links and their domains"
    input_types = [EntityType.URL]
    output_types = [EntityType.URL, EntityType.DOMAIN]
    category = "Web"

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        del config
        source_url = entity.value.strip()
        entities: list[Entity] = []
        edges: list[Edge] = []
        messages: list[str] = []

        if not source_url:
            return TransformResult(messages=["Empty URL value"])

        try:
            async with httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0"},
            ) as client:
                response = await client.get(source_url)
                response.raise_for_status()
        except httpx.TimeoutException:
            return TransformResult(messages=[f"Timeout fetching {source_url}"])
        except httpx.HTTPError as err:
            return TransformResult(messages=[f"HTTP error fetching {source_url}: {err}"])
        except Exception as err:
            return TransformResult(messages=[f"Error fetching {source_url}: {err}"])

        base_url = str(response.url)
        text = response.text or ""
        discovered_urls: set[str] = set()
        discovered_domains: set[str] = set()

        for match in HREF_PATTERN.finditer(text):
            raw_href = (match.group(1) or match.group(2) or match.group(3) or "").strip()
            if not raw_href:
                continue
            if raw_href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            absolute = urljoin(base_url, raw_href)
            parsed = urlparse(absolute)
            if parsed.scheme not in {"http", "https"}:
                continue
            if not parsed.netloc:
                continue
            normalized = parsed.geturl()
            discovered_urls.add(normalized)
            discovered_domains.add(parsed.hostname.lower() if parsed.hostname else "")

            if len(discovered_urls) >= MAX_LINKS:
                break

        discovered_domains.discard("")

        for outbound_url in sorted(discovered_urls):
            out_entity = Entity(
                type=EntityType.URL,
                value=outbound_url,
                properties={"source_page": source_url},
                source=self.name,
            )
            entities.append(out_entity)
            edges.append(
                Edge(
                    source_id=entity.id,
                    target_id=out_entity.id,
                    label="links to",
                    source_transform=self.name,
                )
            )

        for domain in sorted(discovered_domains):
            domain_entity = Entity(
                type=EntityType.DOMAIN,
                value=domain,
                properties={"discovered_from": source_url},
                source=self.name,
            )
            entities.append(domain_entity)
            messages.append(f"Domain: {domain}")

        messages.append(f"Extracted {len(discovered_urls)} outbound link(s)")
        return TransformResult(entities=entities, edges=edges, messages=messages)
