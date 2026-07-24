import httpx

from ogi.models import Entity, Edge, EntityType, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig

INTERESTING_HEADERS = [
    "Server",
    "X-Powered-By",
    "Content-Type",
    "X-Frame-Options",
    "Strict-Transport-Security",
    "Content-Security-Policy",
    "X-Content-Type-Options",
    "X-XSS-Protection",
    "Access-Control-Allow-Origin",
    "Set-Cookie",
]


class URLToHeaders(BaseTransform):
    name = "url_to_headers"
    display_name = "URL to HTTP Headers"
    description = "Performs a HEAD request and extracts interesting HTTP headers from a URL"
    input_types = [EntityType.URL]
    output_types = [EntityType.HTTP_HEADER]
    category = "Web"
    long_description = (
        "Sends a single HEAD request to the URL with a 10 second timeout and follows "
        "redirects, then inspects the response for a fixed list of ten headers of "
        "interest: Server, X-Powered-By, Content-Type, X-Frame-Options, "
        "Strict-Transport-Security, Content-Security-Policy, X-Content-Type-Options, "
        "X-XSS-Protection, Access-Control-Allow-Origin and Set-Cookie. Every one of "
        "those that is present becomes an HTTPHeader entity valued 'Name: value' and "
        "carrying header_name, header_value and http_status_code properties, joined to "
        "the URL by a 'has header' edge. The page body is never downloaded and the HTTP "
        "status code is reported as a message."
    )
    when_to_use = (
        "Use this for lightweight fingerprinting of a web host: identifying the server "
        "software and framework banners, seeing which security headers are set, and "
        "reading cookie flags without pulling page content. Continue with URL to Content "
        "when you need the page text, or URL to Outbound Links to map the site."
    )
    limitations = (
        "Only the ten headers in the built-in list are captured; everything else in the "
        "response is discarded. Some servers reject HEAD or answer it differently from "
        "GET, so headers that only appear on a GET response will be missing. Redirects "
        "are followed, so the headers may belong to the final destination rather than "
        "the URL you supplied. Requests that exceed the 10 second timeout return no "
        "entities."
    )
    example_use_cases = [
        "Fingerprint the web stack behind a URL from its Server and X-Powered-By banners",
        "Check whether a target site sets HSTS, CSP and X-Frame-Options",
        "Record cookie attributes exposed by Set-Cookie on a login page",
    ]

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        url = entity.value
        entities: list[Entity] = []
        edges: list[Edge] = []
        messages: list[str] = []

        try:
            async with httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True,
            ) as client:
                response = await client.head(url)

            messages.append(f"HTTP {response.status_code}")

            for header_name in INTERESTING_HEADERS:
                value = response.headers.get(header_name)
                if value:
                    header_entity = Entity(
                        type=EntityType.HTTP_HEADER,
                        value=f"{header_name}: {value}",
                        properties={
                            "header_name": header_name,
                            "header_value": value,
                            "http_status_code": response.status_code,
                        },
                        source=self.name,
                    )
                    entities.append(header_entity)
                    edges.append(Edge(
                        source_id=entity.id,
                        target_id=header_entity.id,
                        label="has header",
                        source_transform=self.name,
                    ))
                    messages.append(f"{header_name}: {value}")

            if not entities:
                messages.append("No interesting headers found")

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

        return TransformResult(entities=entities, edges=edges, messages=messages)
