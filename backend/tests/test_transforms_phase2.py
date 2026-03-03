import asyncio

import pytest

from ogi.models import Entity, EntityType
from ogi.transforms.base import TransformConfig
from ogi.transforms.cert.cert_transparency import CertTransparency
from ogi.transforms.cert.domain_to_certs import DomainToCerts
from ogi.transforms.email.domain_to_emails import DomainToEmails
from ogi.transforms.email.email_to_domain import EmailToDomain
from ogi.transforms.hash.hash_lookup import HashLookup
from ogi.transforms.ip.ip_to_asn import IPToASN
from ogi.transforms.ip.ip_to_geolocation import IPToGeolocation
from ogi.transforms.social.username_search import UsernameSearch
from ogi.transforms.web.domain_to_urls import DomainToURLs
from ogi.transforms.web.url_to_headers import URLToHeaders
from ogi.transforms.web.url_to_links import URLToLinks


class _FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        json_data=None,
        text: str = "",
        headers: dict[str, str] | None = None,
        url: str = "https://example.com",
    ):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self.headers = headers or {}
        self.url = url

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError("bad status", request=None, response=self)


class _FakeHTTPClient:
    def __init__(self, *, get_response=None, head_response=None):
        self._get_response = get_response
        self._head_response = head_response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str, **kwargs):
        if callable(self._get_response):
            return self._get_response(url)
        return self._get_response

    async def head(self, url: str, **kwargs):
        if callable(self._head_response):
            return self._head_response(url)
        return self._head_response


class _FakeDNSAnswer:
    def __init__(self, value: str):
        self._value = value

    def __str__(self):
        return self._value


@pytest.mark.asyncio
async def test_ip_to_geolocation_with_mocked_http(monkeypatch: pytest.MonkeyPatch):
    transform = IPToGeolocation()
    entity = Entity(type=EntityType.IP_ADDRESS, value="8.8.8.8")

    def fake_client(*args, **kwargs):
        return _FakeHTTPClient(
            get_response=_FakeResponse(
                json_data={
                    "status": "success",
                    "country": "United States",
                    "city": "Mountain View",
                    "regionName": "California",
                    "lat": 37.4,
                    "lon": -122.1,
                    "isp": "Google LLC",
                    "org": "Google Public DNS",
                }
            )
        )

    monkeypatch.setattr("ogi.transforms.ip.ip_to_geolocation.httpx.AsyncClient", fake_client)
    result = await transform.run(entity, TransformConfig())
    assert any(e.type == EntityType.LOCATION for e in result.entities)
    assert any(edge.label == "located in" for edge in result.edges)


@pytest.mark.asyncio
async def test_ip_to_asn_with_mocked_dns(monkeypatch: pytest.MonkeyPatch):
    transform = IPToASN()
    entity = Entity(type=EntityType.IP_ADDRESS, value="8.8.8.8")

    def fake_resolve(query: str, rtype: str):
        assert rtype == "TXT"
        if query.endswith(".origin.asn.cymru.com"):
            return [_FakeDNSAnswer('"15169 | 8.8.8.0/24 | US | arin | 1992-12-01"')]
        return [_FakeDNSAnswer('"15169 | US | arin | 1992-12-01 | Google LLC"')]

    monkeypatch.setattr("ogi.transforms.ip.ip_to_asn.dns.resolver.resolve", fake_resolve)
    result = await transform.run(entity, TransformConfig())
    out_types = {e.type for e in result.entities}
    assert EntityType.AS_NUMBER in out_types
    assert EntityType.ORGANIZATION in out_types


@pytest.mark.asyncio
async def test_url_to_headers_with_mocked_http(monkeypatch: pytest.MonkeyPatch):
    transform = URLToHeaders()
    entity = Entity(type=EntityType.URL, value="https://example.com")

    def fake_client(*args, **kwargs):
        return _FakeHTTPClient(
            head_response=_FakeResponse(
                status_code=200,
                headers={
                    "Server": "nginx",
                    "Content-Type": "text/html",
                },
            )
        )

    monkeypatch.setattr("ogi.transforms.web.url_to_headers.httpx.AsyncClient", fake_client)
    result = await transform.run(entity, TransformConfig())
    assert any(e.type == EntityType.HTTP_HEADER for e in result.entities)
    assert any("Server: nginx" in e.value for e in result.entities)


@pytest.mark.asyncio
async def test_url_to_links_extracts_outbound_links(monkeypatch: pytest.MonkeyPatch):
    transform = URLToLinks()
    entity = Entity(type=EntityType.URL, value="https://source.test")

    html = """
    <html><body>
      <a href="https://alpha.test/a">A</a>
      <a href="/relative/path">B</a>
      <a href="mailto:test@example.com">Mail</a>
    </body></html>
    """

    def fake_client(*args, **kwargs):
        return _FakeHTTPClient(
            get_response=_FakeResponse(text=html, url="https://source.test/base")
        )

    monkeypatch.setattr("ogi.transforms.web.url_to_links.httpx.AsyncClient", fake_client)
    result = await transform.run(entity, TransformConfig())
    out_urls = {e.value for e in result.entities if e.type == EntityType.URL}
    out_domains = {e.value for e in result.entities if e.type == EntityType.DOMAIN}
    assert "https://alpha.test/a" in out_urls
    assert "https://source.test/relative/path" in out_urls
    assert "alpha.test" in out_domains
    assert "source.test" in out_domains


@pytest.mark.asyncio
async def test_domain_to_urls_with_mocked_robots(monkeypatch: pytest.MonkeyPatch):
    transform = DomainToURLs()
    entity = Entity(type=EntityType.DOMAIN, value="example.com")

    robots = "Sitemap: https://example.com/sitemap.xml\nDisallow: /admin\n"

    def fake_client(*args, **kwargs):
        return _FakeHTTPClient(get_response=_FakeResponse(status_code=200, text=robots))

    monkeypatch.setattr("ogi.transforms.web.domain_to_urls.httpx.AsyncClient", fake_client)
    result = await transform.run(entity, TransformConfig())
    assert any(e.type == EntityType.URL for e in result.entities)
    assert any("robots.txt" in msg for msg in result.messages)


@pytest.mark.asyncio
async def test_email_to_domain_extracts_domain():
    transform = EmailToDomain()
    entity = Entity(type=EntityType.EMAIL_ADDRESS, value="alice@example.org")
    result = await transform.run(entity, TransformConfig())
    assert any(e.type == EntityType.DOMAIN and e.value == "example.org" for e in result.entities)


@pytest.mark.asyncio
async def test_domain_to_emails_with_mocked_mx(monkeypatch: pytest.MonkeyPatch):
    transform = DomainToEmails()
    entity = Entity(type=EntityType.DOMAIN, value="example.org")

    class _MX:
        exchange = "mx.example.org."

    monkeypatch.setattr("ogi.transforms.email.domain_to_emails.dns.resolver.resolve", lambda *a, **k: [_MX()])
    result = await transform.run(entity, TransformConfig())
    assert any(e.type == EntityType.EMAIL_ADDRESS for e in result.entities)
    assert any(e.value.startswith("admin@") for e in result.entities)


@pytest.mark.asyncio
async def test_domain_to_certs_with_mocked_certificate(monkeypatch: pytest.MonkeyPatch):
    transform = DomainToCerts()
    entity = Entity(type=EntityType.DOMAIN, value="example.org")

    fake_cert = {
        "subject": ((("commonName", "example.org"), ("organizationName", "Example Org")),),
        "issuer": ((("commonName", "Example Issuer"), ("organizationName", "Issuer Org")),),
        "serialNumber": "ABC123",
        "notBefore": "Jan 1 00:00:00 2026 GMT",
        "notAfter": "Jan 1 00:00:00 2027 GMT",
        "subjectAltName": (("DNS", "example.org"), ("DNS", "www.example.org")),
    }
    monkeypatch.setattr("ogi.transforms.cert.domain_to_certs._fetch_certificate", lambda domain: fake_cert)
    result = await transform.run(entity, TransformConfig())
    out_types = {e.type for e in result.entities}
    assert EntityType.SSL_CERTIFICATE in out_types
    assert EntityType.ORGANIZATION in out_types


@pytest.mark.asyncio
async def test_cert_transparency_with_mocked_http(monkeypatch: pytest.MonkeyPatch):
    transform = CertTransparency()
    entity = Entity(type=EntityType.DOMAIN, value="example.org")

    records = [
        {"common_name": "a.example.org"},
        {"common_name": "b.example.org"},
        {"common_name": "*.example.org"},
    ]

    def fake_client(*args, **kwargs):
        return _FakeHTTPClient(get_response=_FakeResponse(json_data=records))

    monkeypatch.setattr("ogi.transforms.cert.cert_transparency.httpx.AsyncClient", fake_client)
    result = await transform.run(entity, TransformConfig())
    subdomains = [e.value for e in result.entities if e.type == EntityType.SUBDOMAIN]
    assert "a.example.org" in subdomains
    assert "b.example.org" in subdomains


@pytest.mark.asyncio
async def test_hash_lookup_with_mocked_http():
    transform = HashLookup()
    entity = Entity(type=EntityType.HASH, value="d41d8cd98f00b204e9800998ecf8427e")

    class _Client(_FakeHTTPClient):
        async def get(self, url: str, **kwargs):
            return _FakeResponse(
                json_data={
                    "data": {
                        "attributes": {
                            "last_analysis_stats": {
                                "malicious": 1,
                                "harmless": 4,
                            },
                            "type_description": "Win32 EXE",
                            "size": 1234,
                        }
                    }
                }
            )

    import ogi.transforms.hash.hash_lookup as mod

    original = mod.httpx.AsyncClient
    mod.httpx.AsyncClient = lambda *a, **k: _Client()
    try:
        result = await transform.run(entity, TransformConfig(settings={"virustotal_api_key": "x"}))
    finally:
        mod.httpx.AsyncClient = original

    assert any(e.type == EntityType.HASH for e in result.entities)
    assert any("Detection ratio:" in msg for msg in result.messages)


@pytest.mark.asyncio
async def test_username_search_with_mocked_http(monkeypatch: pytest.MonkeyPatch):
    transform = UsernameSearch()
    entity = Entity(type=EntityType.PERSON, value="alice")

    def fake_head(url: str):
        if "github.com" in url:
            return _FakeResponse(status_code=200)
        return _FakeResponse(status_code=404)

    def fake_client(*args, **kwargs):
        return _FakeHTTPClient(head_response=fake_head)

    async def no_sleep(_seconds: float):
        return None

    monkeypatch.setattr("ogi.transforms.social.username_search.httpx.AsyncClient", fake_client)
    monkeypatch.setattr("ogi.transforms.social.username_search.asyncio.sleep", no_sleep)
    result = await transform.run(entity, TransformConfig())
    assert any(e.type == EntityType.SOCIAL_MEDIA for e in result.entities)
    assert any(e.type == EntityType.URL for e in result.entities)
    assert any("GitHub" in msg for msg in result.messages)
