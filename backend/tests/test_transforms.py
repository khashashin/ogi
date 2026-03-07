import asyncio
from uuid import uuid4

import pytest

from ogi.models import Entity, EntityType
from ogi.store.location_search_store import LocationGeocodeResult, LocationSearchStore
from ogi.store.sun_store import SunStore
from ogi.store.timezone_store import TimezoneResolution, TimezoneStore
from ogi.store.weather_store import WeatherSnapshot, WeatherStore
from ogi.transforms.base import TransformConfig
from ogi.transforms.cert.cert_transparency import CertTransparency
from ogi.transforms.cert.domain_to_certs import DomainToCerts
from ogi.transforms.email.domain_to_emails import DomainToEmails
from ogi.transforms.email.email_to_domain import EmailToDomain
from ogi.transforms.hash.hash_lookup import HashLookup
from ogi.transforms.ip.ip_to_asn import IPToASN
from ogi.transforms.ip.ip_to_geolocation import IPToGeolocation
from ogi.transforms.location.location_to_geocode import LocationToGeocode
from ogi.transforms.location.location_to_sun_times import LocationToSunTimes
from ogi.transforms.location.location_to_timezone import LocationToTimezone
from ogi.transforms.location.location_to_weather_snapshot import LocationToWeatherSnapshot
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


class _FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    def __init__(self, cache_row=None):
        self.cache_row = cache_row
        self.added: list[object] = []
        self.commits = 0

    async def execute(self, stmt):
        return _FakeScalarResult(self.cache_row)

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1


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
        assert "verify" not in kwargs
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
        assert "verify" not in kwargs
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
        assert "verify" not in kwargs
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


@pytest.mark.asyncio
async def test_location_search_normalize_cache_hit(monkeypatch: pytest.MonkeyPatch):
    from ogi.models import GeocodeCache

    cached = GeocodeCache(
        query="zurich, switzerland",
        lat=47.3769,
        lon=8.5417,
        display_name="Zurich, Switzerland",
        confidence=0.88,
        source="cache",
    )
    store = LocationSearchStore(_FakeSession(cache_row=cached))

    async def fail_upstream(_query: str):
        raise AssertionError("Upstream should not be called on cache hit")

    monkeypatch.setattr(store, "_fetch_nominatim_detail", fail_upstream)

    result = await store.normalize("Zurich, Switzerland")
    assert result.cache_hit is True
    assert result.source == "cache"
    assert result.display_name == "Zurich, Switzerland"
    assert result.lat == pytest.approx(47.3769)
    assert result.lon == pytest.approx(8.5417)


@pytest.mark.asyncio
async def test_location_search_normalize_upstream_parse_and_cache(monkeypatch: pytest.MonkeyPatch):
    session = _FakeSession(cache_row=None)
    store = LocationSearchStore(session)
    captured: list[tuple[str, str, float]] = []

    async def fake_upstream(_query: str):
        return LocationGeocodeResult(
            query="Berlin",
            lat=52.52,
            lon=13.405,
            display_name="Berlin, Germany",
            confidence=0.83,
            source="nominatim",
            country="Germany",
            region="Berlin",
            city="Berlin",
            postcode="10117",
        )

    async def capture_upsert(query: str, suggestion, confidence: float = 0.6):
        captured.append((query, suggestion.display_name, confidence))

    monkeypatch.setattr(store, "_fetch_nominatim_detail", fake_upstream)
    monkeypatch.setattr(store, "_upsert_cache", capture_upsert)

    result = await store.normalize("Berlin")
    assert result.source == "nominatim"
    assert result.cache_hit is False
    assert result.country == "Germany"
    assert result.region == "Berlin"
    assert result.city == "Berlin"
    assert result.postcode == "10117"
    assert captured[0] == ("berlin", "Berlin, Germany", 0.83)


@pytest.mark.asyncio
async def test_location_search_normalize_rate_limited(monkeypatch: pytest.MonkeyPatch):
    import time as _time

    store = LocationSearchStore(_FakeSession(cache_row=None))
    LocationSearchStore._cooldown_until = _time.time() + 30
    try:
        async def fail_upstream(_query: str):
            raise AssertionError("Upstream should not be called while rate-limited")

        monkeypatch.setattr(store, "_fetch_nominatim_detail", fail_upstream)
        result = await store.normalize("London")
        assert result.rate_limited is True
        assert result.source == "rate-limit"
        assert (result.retry_after_seconds or 0) > 0
    finally:
        LocationSearchStore._cooldown_until = 0.0


@pytest.mark.asyncio
async def test_location_to_geocode_with_mocked_store(monkeypatch: pytest.MonkeyPatch):
    transform = LocationToGeocode()
    entity = Entity(type=EntityType.LOCATION, value="NYC", project_id=uuid4())

    class _SessionCtx:
        def __aiter__(self):
            return self

        async def __anext__(self):
            if getattr(self, "_done", False):
                raise StopAsyncIteration
            self._done = True
            return _FakeSession()

    async def fake_normalize(self, query: str):
        assert query == "NYC"
        return LocationGeocodeResult(
            query=query,
            lat=40.7128,
            lon=-74.0060,
            display_name="New York, NY, USA",
            confidence=0.84,
            source="nominatim",
            country="USA",
            region="New York",
            city="New York",
            postcode="10007",
        )

    monkeypatch.setattr("ogi.transforms.location.location_to_geocode.get_session", lambda: _SessionCtx())
    monkeypatch.setattr(LocationSearchStore, "normalize", fake_normalize)

    result = await transform.run(entity, TransformConfig())
    assert len(result.entities) == 1
    out = result.entities[0]
    assert out.type == EntityType.LOCATION
    assert out.value == "New York, NY, USA"
    assert out.properties["lat"] == pytest.approx(40.7128)
    assert out.properties["lon"] == pytest.approx(-74.0060)
    assert out.properties["country"] == "USA"
    assert any(msg == "Confidence: 0.84." for msg in result.messages)
    assert any(msg == "Used upstream geocoder." for msg in result.messages)


@pytest.mark.asyncio
async def test_location_to_timezone_known_coordinate_mapping(monkeypatch: pytest.MonkeyPatch):
    transform = LocationToTimezone()
    entity = Entity(
        type=EntityType.LOCATION,
        value="Zurich",
        project_id=uuid4(),
        properties={"lat": 47.3769, "lon": 8.5417},
    )

    def fake_resolve(self, lat: float, lon: float, observed_at=None):
        assert lat == pytest.approx(47.3769)
        assert lon == pytest.approx(8.5417)
        return TimezoneResolution(
            timezone="Europe/Zurich",
            utc_offset="+01:00",
            dst_active=False,
            cache_hit=False,
        )

    monkeypatch.setattr(TimezoneStore, "resolve", fake_resolve)

    result = await transform.run(entity, TransformConfig())
    assert len(result.entities) == 1
    out = result.entities[0]
    assert out.properties["timezone"] == "Europe/Zurich"
    assert out.properties["utc_offset"] == "+01:00"
    assert out.properties["dst_active"] is False
    assert any(msg == "Timezone: Europe/Zurich." for msg in result.messages)


@pytest.mark.asyncio
async def test_location_to_timezone_missing_coordinate_behavior(monkeypatch: pytest.MonkeyPatch):
    transform = LocationToTimezone()
    entity = Entity(type=EntityType.LOCATION, value="Unknown place", project_id=uuid4())

    class _SessionCtx:
        def __aiter__(self):
            return self

        async def __anext__(self):
            if getattr(self, "_done", False):
                raise StopAsyncIteration
            self._done = True
            return _FakeSession()

    async def fake_normalize(self, query: str):
        assert query == "Unknown place"
        return LocationGeocodeResult(query=query, source="nominatim")

    monkeypatch.setattr("ogi.transforms.location.location_to_timezone.get_session", lambda: _SessionCtx(), raising=False)
    monkeypatch.setattr(LocationToTimezone, "_get_session", staticmethod(lambda: _SessionCtx()))
    monkeypatch.setattr(LocationSearchStore, "normalize", fake_normalize)

    result = await transform.run(entity, TransformConfig())
    assert result.entities == []
    assert result.messages == ["Timezone lookup skipped: missing valid coordinates."]


def test_sun_store_typical_latitude_date():
    from datetime import datetime, timezone

    result = SunStore().calculate(
        lat=47.3769,
        lon=8.5417,
        reference_time=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
        timezone_name="Europe/Zurich",
    )
    assert result.error is None
    assert result.sunrise_utc is not None
    assert result.sunset_utc is not None
    assert result.civil_twilight_begin_utc is not None
    assert result.civil_twilight_end_utc is not None
    assert result.nautical_twilight_begin_utc is not None
    assert result.astronomical_twilight_end_utc is not None
    assert result.sunrise_local is not None
    assert result.sunset_local is not None
    assert result.daylight_at_reference is True


def test_sun_store_polar_region_edge_case():
    from datetime import datetime, timezone

    result = SunStore().calculate(
        lat=78.2232,
        lon=15.6469,
        reference_time=datetime(2026, 12, 15, 12, 0, tzinfo=timezone.utc),
        timezone_name="Arctic/Longyearbyen",
    )
    assert result.error is None
    assert result.sunrise_utc is None
    assert result.sunset_utc is None
    assert result.polar_note is not None


@pytest.mark.asyncio
async def test_location_to_sun_times_with_explicit_target_datetime(monkeypatch: pytest.MonkeyPatch):
    from datetime import datetime, timezone

    transform = LocationToSunTimes()
    entity = Entity(
        type=EntityType.LOCATION,
        value="Zurich",
        project_id=uuid4(),
        properties={"lat": 47.3769, "lon": 8.5417, "timezone": "Europe/Zurich"},
    )
    captured: dict[str, object] = {}
    original_calculate = SunStore.calculate

    def fake_calculate(self, lat: float, lon: float, reference_time: datetime, timezone_name: str | None = None):
        captured["reference_time"] = reference_time
        captured["timezone_name"] = timezone_name
        return original_calculate(self, lat, lon, reference_time, timezone_name)

    monkeypatch.setattr(SunStore, "calculate", fake_calculate)
    result = await transform.run(
        entity,
        TransformConfig(settings={"target_datetime": "2026-06-15T10:30:00Z"}),
    )
    assert result.entities
    assert captured["reference_time"] == datetime(2026, 6, 15, 10, 30, tzinfo=timezone.utc)
    out = result.entities[0]
    assert out.properties["sunrise_utc"] is not None
    assert out.properties["sunset_utc"] is not None
    assert out.properties["daylight_at_reference_time"] is True


@pytest.mark.asyncio
async def test_weather_store_parses_current_weather(monkeypatch: pytest.MonkeyPatch):
    WeatherStore._cache.clear()
    store = WeatherStore()

    def fake_client(*args, **kwargs):
        return _FakeHTTPClient(
            get_response=_FakeResponse(
                json_data={
                    "weather": [{"description": "light rain"}],
                    "main": {"temp": 12.3},
                    "wind": {"speed": 5.0},
                    "visibility": 9000,
                    "dt": 1741356000,
                }
            )
        )

    monkeypatch.setattr("ogi.store.weather_store.httpx.AsyncClient", fake_client)
    snapshot = await store.get_snapshot(47.37, 8.54, None, "ow-test")
    assert snapshot.condition == "light rain"
    assert snapshot.temp_c == pytest.approx(12.3)
    assert snapshot.wind_kph == pytest.approx(18.0)
    assert snapshot.visibility_km == pytest.approx(9.0)
    assert snapshot.source_timestamp is not None


@pytest.mark.asyncio
async def test_weather_store_parses_historical_weather(monkeypatch: pytest.MonkeyPatch):
    from datetime import datetime, timezone

    WeatherStore._cache.clear()
    store = WeatherStore()
    observed = datetime(2026, 3, 7, 12, 0, tzinfo=timezone.utc)

    def fake_client(*args, **kwargs):
        return _FakeHTTPClient(
            get_response=_FakeResponse(
                json_data={
                    "data": [
                        {
                            "dt": 1741348800,
                            "temp": 7.8,
                            "wind_speed": 3.0,
                            "visibility": 7000,
                            "weather": [{"main": "Clouds"}],
                        }
                    ]
                }
            )
        )

    monkeypatch.setattr("ogi.store.weather_store.httpx.AsyncClient", fake_client)
    snapshot = await store.get_snapshot(46.95, 7.44, observed, "ow-test")
    assert snapshot.condition == "Clouds"
    assert snapshot.temp_c == pytest.approx(7.8)
    assert snapshot.wind_kph == pytest.approx(10.8)
    assert snapshot.visibility_km == pytest.approx(7.0)


@pytest.mark.asyncio
async def test_location_to_weather_snapshot_provider_error_fallback(monkeypatch: pytest.MonkeyPatch):
    WeatherStore._cache.clear()
    transform = LocationToWeatherSnapshot()
    entity = Entity(
        type=EntityType.LOCATION,
        value="Zurich",
        project_id=uuid4(),
        properties={"lat": 47.37, "lon": 8.54},
    )

    def fake_client(*args, **kwargs):
        return _FakeHTTPClient(get_response=_FakeResponse(status_code=429, json_data={}))

    monkeypatch.setattr("ogi.store.weather_store.httpx.AsyncClient", fake_client)
    result = await transform.run(entity, TransformConfig(settings={"openweather_api_key": "ow-test"}))
    assert result.entities == []
    assert result.messages == ["OpenWeather rate limit exceeded."]


@pytest.mark.asyncio
async def test_location_to_weather_snapshot_missing_coordinate_behavior():
    WeatherStore._cache.clear()
    transform = LocationToWeatherSnapshot()
    entity = Entity(type=EntityType.LOCATION, value="Unknown", project_id=uuid4())
    result = await transform.run(entity, TransformConfig(settings={"openweather_api_key": "ow-test"}))
    assert result.entities == []
    assert result.messages == ["Weather lookup skipped: missing valid coordinates."]


@pytest.mark.asyncio
async def test_location_to_weather_snapshot_uses_explicit_target_datetime_over_observed_at(monkeypatch: pytest.MonkeyPatch):
    from datetime import datetime, timezone

    WeatherStore._cache.clear()
    transform = LocationToWeatherSnapshot()
    entity = Entity(
        type=EntityType.LOCATION,
        value="Zurich",
        project_id=uuid4(),
        properties={
            "lat": 47.37,
            "lon": 8.54,
            "observed_at": "2026-03-07T09:00:00Z",
        },
    )
    captured: dict[str, object] = {}

    async def fake_get_snapshot(self, lat: float, lon: float, observed_at, api_key: str):
        captured["lat"] = lat
        captured["lon"] = lon
        captured["observed_at"] = observed_at
        captured["api_key"] = api_key
        return WeatherSnapshot(
            condition="Clear",
            temp_c=14.2,
            wind_kph=9.0,
            visibility_km=10.0,
            source_timestamp="2026-03-06T10:30:00+00:00",
        )

    monkeypatch.setattr(WeatherStore, "get_snapshot", fake_get_snapshot)
    result = await transform.run(
        entity,
        TransformConfig(
            settings={
                "openweather_api_key": "ow-test",
                "target_datetime": "2026-03-06T10:30:00Z",
            }
        ),
    )
    assert result.entities
    assert captured["observed_at"] == datetime(2026, 3, 6, 10, 30, tzinfo=timezone.utc)
    assert any(msg == "Requested timestamp: 2026-03-06T10:30:00+00:00." for msg in result.messages)


@pytest.mark.asyncio
async def test_location_to_weather_snapshot_rejects_invalid_target_datetime():
    WeatherStore._cache.clear()
    transform = LocationToWeatherSnapshot()
    entity = Entity(
        type=EntityType.LOCATION,
        value="Zurich",
        project_id=uuid4(),
        properties={"lat": 47.37, "lon": 8.54},
    )
    result = await transform.run(
        entity,
        TransformConfig(settings={"openweather_api_key": "ow-test", "target_datetime": "not-a-date"}),
    )
    assert result.entities == []
    assert result.messages == ["Weather lookup skipped: invalid target_datetime. Use ISO-8601 format."]


@pytest.mark.asyncio
async def test_weather_store_historical_unavailable_message(monkeypatch: pytest.MonkeyPatch):
    from datetime import datetime, timezone

    WeatherStore._cache.clear()
    store = WeatherStore()
    observed = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)

    def fake_client(*args, **kwargs):
        return _FakeHTTPClient(get_response=_FakeResponse(status_code=403, json_data={}))

    monkeypatch.setattr("ogi.store.weather_store.httpx.AsyncClient", fake_client)
    snapshot = await store.get_snapshot(46.95, 7.44, observed, "ow-test")
    assert snapshot.error == "Historical weather is unavailable for the requested timestamp or current OpenWeather plan."


@pytest.mark.asyncio
async def test_weather_store_historical_401_reports_plan_or_key_issue(monkeypatch: pytest.MonkeyPatch):
    from datetime import datetime, timezone

    WeatherStore._cache.clear()
    store = WeatherStore()
    observed = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)

    def fake_client(*args, **kwargs):
        return _FakeHTTPClient(get_response=_FakeResponse(status_code=401, json_data={}))

    monkeypatch.setattr("ogi.store.weather_store.httpx.AsyncClient", fake_client)
    snapshot = await store.get_snapshot(46.95, 7.44, observed, "ow-test")
    assert snapshot.error == "Historical weather is unavailable for this API key or current OpenWeather plan."
