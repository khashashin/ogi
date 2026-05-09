import pytest
import sys
from types import ModuleType

from ogi.config import settings
from ogi.models import Entity, EntityType
from ogi.engine.transform_engine import TransformEngine
from ogi.models import Project
from ogi.transforms.base import TransformConfig
from ogi.transforms.web.url_to_content import URLToContent


@pytest.fixture
def engine():
    e = TransformEngine()
    e.auto_discover()
    return e


def test_auto_discover(engine: TransformEngine):
    transforms = engine.list_transforms()
    names = {t.name for t in transforms}
    expected = {
        "domain_to_ip",
        "domain_to_mx",
        "domain_to_ns",
        "ip_to_domain",
        "person_to_usernames",
        "whois_lookup",
        "website_to_people",
        "location_to_geocode",
        "location_to_nearby_asns",
        "location_to_reverse_geocode",
        "location_to_weather_snapshot",
        "url_to_links",
        "url_to_content",
        "content_to_iocs",
    }
    assert expected <= names
    assert len(names) == len(transforms)


def test_list_for_entity(engine: TransformEngine):
    domain = Entity(type=EntityType.DOMAIN, value="example.com")
    transforms = engine.list_for_entity(domain)
    names = [t.name for t in transforms]
    assert "domain_to_ip" in names
    assert "domain_to_mx" in names
    assert "domain_to_ns" in names
    assert "whois_lookup" in names
    # ip_to_domain should NOT be listed for domain entity
    assert "ip_to_domain" not in names


def test_list_for_person_entity(engine: TransformEngine):
    person = Entity(type=EntityType.PERSON, value="Alice Example")
    transforms = engine.list_for_entity(person)
    names = [t.name for t in transforms]
    assert "person_to_usernames" in names
    assert "username_search" not in names


def test_list_for_ip_entity(engine: TransformEngine):
    ip = Entity(type=EntityType.IP_ADDRESS, value="1.2.3.4")
    transforms = engine.list_for_entity(ip)
    names = [t.name for t in transforms]
    assert "ip_to_domain" in names
    assert "domain_to_ip" not in names


@pytest.mark.asyncio
async def test_content_to_iocs_extracts_common_indicators(engine: TransformEngine):
    transform = engine.get_transform("content_to_iocs")
    assert transform is not None
    # Force deterministic regex extraction regardless of optional iocsearcher availability.
    import ogi.transforms.web.content_to_iocs as content_to_iocs_module

    original_import_module = content_to_iocs_module.importlib.import_module
    content_to_iocs_module.importlib.import_module = lambda _name: (_ for _ in ()).throw(
        ModuleNotFoundError("iocsearcher unavailable for test")
    )
    document = Entity(
        type=EntityType.DOCUMENT,
        value="Security report",
        properties={
            "content": (
                "Indicators: admin@example.org 8.8.8.8 https://evil.example/path "
                "d41d8cd98f00b204e9800998ecf8427e and evil.example."
            )
        },
    )

    try:
        result = await transform.run(document, TransformConfig(settings={}))
    finally:
        content_to_iocs_module.importlib.import_module = original_import_module
    out_types = {entity.type for entity in result.entities}
    out_values = {entity.value for entity in result.entities}

    assert EntityType.EMAIL_ADDRESS in out_types
    assert EntityType.IP_ADDRESS in out_types
    assert EntityType.HASH in out_types
    assert EntityType.DOMAIN in out_types
    assert "admin@example.org" in out_values
    assert "8.8.8.8" in out_values
    assert "https://evil.example/path" in out_values
    assert "d41d8cd98f00b204e9800998ecf8427e" in out_values
    assert "evil.example" in out_values
    assert any("regex fallback" in msg.lower() for msg in result.messages)


@pytest.mark.asyncio
async def test_content_to_iocs_uses_iocsearcher_when_available(engine: TransformEngine):
    transform = engine.get_transform("content_to_iocs")
    assert transform is not None

    fake_searcher_module = ModuleType("iocsearcher.searcher")

    class FakeIOC:
        def __init__(self, name: str, value: str):
            self.name = name
            self.value = value

    class FakeSearcher:
        def search_data(self, text: str):
            assert "8.8.4.4" in text
            return [
                FakeIOC("ipv4", "8.8.4.4"),
                FakeIOC("email", "ioc@example.org"),
                FakeIOC("url", "https://ioc.example/path"),
            ]

    fake_searcher_module.Searcher = FakeSearcher
    sys.modules["iocsearcher"] = ModuleType("iocsearcher")
    sys.modules["iocsearcher.searcher"] = fake_searcher_module

    try:
        document = Entity(
            type=EntityType.DOCUMENT,
            value="IOC doc",
            properties={"content": "Data: 8.8.4.4 ioc@example.org https://ioc.example/path"},
        )
        result = await transform.run(document, TransformConfig(settings={}))
        out_values = {entity.value for entity in result.entities}
        assert "8.8.4.4" in out_values
        assert "ioc@example.org" in out_values
        assert "https://ioc.example/path" in out_values
        assert any("iocsearcher" in msg.lower() for msg in result.messages)
    finally:
        sys.modules.pop("iocsearcher.searcher", None)
        sys.modules.pop("iocsearcher", None)


def test_url_to_content_blocks_localhost_by_default(engine: TransformEngine):
    transform = engine.get_transform("url_to_content")
    assert transform is not None
    assert transform._is_blocked_host("localhost") is True
    assert transform._is_blocked_host("127.0.0.1") is True
    assert transform._is_blocked_host("10.1.2.3") is True
    assert transform._is_blocked_host("example.org") is False


def test_get_transform(engine: TransformEngine):
    t = engine.get_transform("domain_to_ip")
    assert t is not None
    assert t.display_name == "Domain to IP Address"
    assert t.category == "DNS"


def test_get_nonexistent_transform(engine: TransformEngine):
    assert engine.get_transform("nonexistent") is None


def test_transform_setting_max_override_updates_schema_and_runtime(monkeypatch):
    monkeypatch.setattr(
        settings,
        "transform_setting_max_overrides",
        {"max_content_chars": 50},
    )

    effective = URLToContent.effective_settings()
    max_content_chars = next(
        setting for setting in effective if setting.name == "max_content_chars"
    )

    assert max_content_chars.max_value == 50
    assert URLToContent.parse_int_setting(
        "500",
        setting_name="max_content_chars",
        default=12000,
        min_value=100,
        declared_max=200000,
    ) == 50


def test_transform_setting_max_override_can_disable_cap(monkeypatch):
    monkeypatch.setattr(
        settings,
        "transform_setting_max_overrides",
        {"max_results": None},
    )

    assert URLToContent.get_effective_setting_max("max_results", 500) is None


@pytest.mark.asyncio
async def test_website_to_people_requires_openai_key(engine: TransformEngine):
    transform = engine.get_transform("website_to_people")
    assert transform is not None
    website = Entity(type=EntityType.DOMAIN, value="example.org")
    result = await transform.run(website, TransformConfig(settings={}))
    assert result.messages
    assert "OpenAI API key required" in result.messages[0]


@pytest.mark.asyncio
async def test_run_transform_wrong_type(engine: TransformEngine):
    ip = Entity(type=EntityType.IP_ADDRESS, value="1.2.3.4")
    project = Project(name="test")

    with pytest.raises(ValueError, match="cannot run on"):
        await engine.run_transform("domain_to_ip", ip, project.id)
