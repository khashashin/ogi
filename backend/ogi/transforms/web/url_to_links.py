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


class URLToLinks(BaseTransform):
    name = "url_to_links"
    display_name = "URL to Outbound Links"
    description = "Fetches a page and extracts outbound links and their domains"
    input_types = [EntityType.URL]
    output_types = [EntityType.URL, EntityType.DOMAIN]
    category = "Web"
    long_description = (
        "Fetches the page with an HTTP GET (10 second timeout, redirects followed, a "
        "Mozilla/5.0 User-Agent) and scans the returned HTML with a regular expression "
        "over href attributes of <a> tags. Fragment, javascript:, mailto: and tel: "
        "targets are skipped; the rest are resolved against the final URL after "
        "redirects and kept only when they are http or https and have a hostname. Each "
        "unique link becomes a URL entity carrying source_page and is joined to the "
        "input URL by a 'links to' edge, while each distinct hostname is also emitted as "
        "a Domain entity with a discovered_from property but no edge. Collection stops "
        "at 100 links by default, a cap the server can raise or lower through its "
        "transform setting maximum overrides."
    )
    when_to_use = (
        "Use this to expand a single page into the pages and sites it references, "
        "whether you are mapping a site's structure, tracing outbound referrals from a "
        "landing page, or spotting third-party hosts embedded in the markup. The Domain "
        "entities it emits feed straight into Domain to IP Address, WHOIS Lookup or "
        "Domain to SSL Certificates."
    )
    limitations = (
        "Reads only the HTML the server returns, so links written into the page by "
        "JavaScript after load are never seen; use URL to Content when the page is "
        "rendered client-side. Extraction is regex-based over <a> tags, so hrefs inside "
        "commented-out markup can be picked up and links carried by other elements such "
        "as iframe, script or link are ignored. The cap is applied while parsing, so a "
        "truncated result is whatever appeared first in the document rather than a "
        "ranked selection. Domain entities are created unconnected to the source page."
    )
    example_use_cases = [
        "Map the outbound link graph of a suspicious landing page",
        "Collect the third-party domains embedded in a target website",
        "Gather sibling pages to feed into URL to Content for text extraction",
    ]

    async def run(self, entity: Entity, _config: TransformConfig) -> TransformResult:
        source_url = entity.value.strip()
        entities: list[Entity] = []
        edges: list[Edge] = []
        messages: list[str] = []
        max_links = self.get_effective_setting_max("max_links", 100)

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

            if max_links is not None and len(discovered_urls) >= int(max_links):
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
