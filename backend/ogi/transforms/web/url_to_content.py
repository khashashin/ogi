from __future__ import annotations

import html
import ipaddress
import re
from urllib.parse import urlparse

import httpx

from ogi.models import Edge, Entity, EntityType, TransformResult
from ogi.transforms.base import BaseTransform, TransformConfig, TransformSetting

DEFAULT_MAX_DOWNLOAD_BYTES = 2_000_000
ALLOWED_TEXT_CONTENT_TYPES = (
    "text/",
    "application/json",
    "application/xml",
    "application/xhtml+xml",
    "application/javascript",
    "application/x-javascript",
)


class URLToContent(BaseTransform):
    name = "url_to_content"
    display_name = "URL to Content"
    description = "Fetches a URL and extracts readable text content into a Document entity"
    input_types = [EntityType.URL]
    output_types = [EntityType.DOCUMENT]
    category = "Web"
    settings = [
        TransformSetting(
            name="max_content_chars",
            display_name="Max Content Chars",
            description="Maximum number of extracted text characters to keep",
            default="12000",
            field_type="integer",
            min_value=1000,
            max_value=200000,
        ),
        TransformSetting(
            name="max_download_bytes",
            display_name="Max Download Bytes",
            description="Maximum HTTP response bytes to download",
            default=str(DEFAULT_MAX_DOWNLOAD_BYTES),
            field_type="integer",
            min_value=50_000,
            max_value=20_000_000,
        ),
        TransformSetting(
            name="parse_with_bs4",
            display_name="Parse with BeautifulSoup",
            description="Use BeautifulSoup parser for HTML if available",
            default="true",
            field_type="boolean",
        ),
        TransformSetting(
            name="render_js",
            display_name="Render JavaScript",
            description="Use Playwright for dynamic pages if installed",
            default="false",
            field_type="boolean",
        ),
        TransformSetting(
            name="allow_local_network",
            display_name="Allow Local Network",
            description="Allow localhost and private IP targets",
            default="false",
            field_type="boolean",
        ),
    ]

    async def run(self, entity: Entity, config: TransformConfig) -> TransformResult:
        url = entity.value.strip()
        entities: list[Entity] = []
        edges: list[Edge] = []
        messages: list[str] = []

        if not url:
            return TransformResult(messages=["Empty URL value"])

        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return TransformResult(messages=["Only http:// and https:// URLs are supported"])

        allow_local = self._parse_bool(
            config.settings.get("allow_local_network", "false"),
            default=False,
        )
        if not allow_local and self._is_blocked_host(parsed.hostname or ""):
            return TransformResult(messages=[f"Blocked potentially unsafe target host: {parsed.hostname}"])

        max_chars = self._parse_positive_int(
            config.settings.get("max_content_chars", "12000"),
            default=12000,
        )
        max_download = self._parse_positive_int(
            config.settings.get("max_download_bytes", str(DEFAULT_MAX_DOWNLOAD_BYTES)),
            default=DEFAULT_MAX_DOWNLOAD_BYTES,
        )
        parse_with_bs4 = self._parse_bool(config.settings.get("parse_with_bs4", "true"), default=True)
        render_js = self._parse_bool(config.settings.get("render_js", "false"), default=False)

        try:
            if render_js:
                raw, final_url, content_type = await self._fetch_with_playwright(url, max_chars)
                messages.append("Playwright rendering used")
            else:
                raw, final_url, content_type = await self._safe_fetch_http(url, max_download)

            text = self._extract_text(raw, content_type, parse_with_bs4=parse_with_bs4)
            text = text[:max_chars] if max_chars > 0 else text
            if not text.strip():
                return TransformResult(messages=[f"No readable content extracted from {final_url}"])

            title = self._extract_title(raw, parse_with_bs4=parse_with_bs4)
            final_host = urlparse(final_url).hostname or urlparse(url).hostname or url
            value = title or final_host
            document = Entity(
                type=EntityType.DOCUMENT,
                value=value,
                properties={
                    "url": final_url,
                    "content": text,
                    "content_type": content_type,
                    "title": title,
                    "content_length": len(text),
                },
                source=self.name,
            )
            entities.append(document)
            edges.append(
                Edge(
                    source_id=entity.id,
                    target_id=document.id,
                    label="has content",
                    source_transform=self.name,
                )
            )
            messages.append(f"Fetched content from {final_url}")
            messages.append(f"Extracted {len(text)} characters")

        except httpx.TimeoutException:
            messages.append(f"Timeout connecting to {url}")
        except httpx.ConnectError:
            messages.append(f"Connection error for {url}")
        except httpx.HTTPStatusError as err:
            messages.append(f"HTTP error for {url}: {err.response.status_code}")
        except httpx.HTTPError as err:
            messages.append(f"HTTP error for {url}: {err}")
        except Exception as err:
            messages.append(f"Error fetching content from {url}: {err}")

        return TransformResult(entities=entities, edges=edges, messages=messages)

    @staticmethod
    def _parse_positive_int(raw: str, default: int) -> int:
        try:
            value = int(raw)
            if value <= 0:
                return default
            return value
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _parse_bool(raw: str, default: bool) -> bool:
        if raw is None:
            return default
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _is_blocked_host(hostname: str) -> bool:
        host = hostname.strip().lower()
        if not host:
            return True
        if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
            return True
        try:
            ip = ipaddress.ip_address(host)
            return (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
            )
        except ValueError:
            return False

    @staticmethod
    def _is_allowed_content_type(content_type: str) -> bool:
        lower = (content_type or "").lower()
        return any(lower.startswith(prefix) for prefix in ALLOWED_TEXT_CONTENT_TYPES)

    async def _safe_fetch_http(self, url: str, max_download_bytes: int) -> tuple[str, str, str]:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                content_type = (response.headers.get("content-type") or "").lower().split(";")[0].strip()
                if content_type and not self._is_allowed_content_type(content_type):
                    raise ValueError(f"Blocked non-text content type: {content_type}")

                size = 0
                chunks: list[bytes] = []
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > max_download_bytes:
                        raise ValueError(f"Response exceeded size limit ({max_download_bytes} bytes)")
                    chunks.append(chunk)

                body = b"".join(chunks)
                if b"\x00" in body:
                    raise ValueError("Blocked binary-looking payload")
                text = body.decode(response.encoding or "utf-8", errors="replace")
                return text, str(response.url), content_type

    async def _fetch_with_playwright(self, url: str, max_chars: int) -> tuple[str, str, str]:
        try:
            from playwright.async_api import async_playwright  # type: ignore
        except Exception as err:
            raise ValueError(f"Playwright requested but not available: {err}") from err

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                response = await page.goto(url, wait_until="networkidle", timeout=20_000)
                if response is None:
                    raise ValueError("No response received in browser")
                if response.status >= 400:
                    raise ValueError(f"HTTP error for {url}: {response.status}")

                html_content = await page.content()
                final_url = page.url
                content_type = (response.headers.get("content-type") or "").split(";")[0].strip().lower()
                if content_type and not self._is_allowed_content_type(content_type):
                    raise ValueError(f"Blocked non-text content type: {content_type}")
                if max_chars > 0:
                    html_content = html_content[: max_chars * 4]
                return html_content, final_url, content_type or "text/html"
            finally:
                await browser.close()

    @staticmethod
    def _extract_text(raw: str, content_type: str, parse_with_bs4: bool) -> str:
        lower_ct = (content_type or "").lower()
        if "html" not in lower_ct:
            return URLToContent._normalize_space(raw)

        if parse_with_bs4:
            try:
                from bs4 import BeautifulSoup  # type: ignore

                soup = BeautifulSoup(raw, "html.parser")
                for tag in soup(["script", "style", "noscript"]):
                    tag.decompose()
                return URLToContent._normalize_space(soup.get_text(" ", strip=True))
            except Exception:
                pass

        no_script = re.sub(r"(?is)<script.*?>.*?</script>", " ", raw)
        no_style = re.sub(r"(?is)<style.*?>.*?</style>", " ", no_script)
        no_tags = re.sub(r"(?s)<[^>]+>", " ", no_style)
        return URLToContent._normalize_space(html.unescape(no_tags))

    @staticmethod
    def _extract_title(raw: str, parse_with_bs4: bool) -> str:
        if parse_with_bs4:
            try:
                from bs4 import BeautifulSoup  # type: ignore

                soup = BeautifulSoup(raw, "html.parser")
                if soup.title and soup.title.string:
                    return URLToContent._normalize_space(html.unescape(soup.title.string))
            except Exception:
                pass
        match = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw)
        if not match:
            return ""
        return URLToContent._normalize_space(html.unescape(match.group(1)))

    @staticmethod
    def _normalize_space(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()
