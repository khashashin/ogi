import pytest

from ogi.models import Entity, EntityType, TransformStatus
from ogi.engine.transform_engine import TransformEngine
from ogi.models import Project


@pytest.fixture
def engine():
    e = TransformEngine()
    e.auto_discover()
    return e


def test_auto_discover(engine: TransformEngine):
    transforms = engine.list_transforms()
    names = [t.name for t in transforms]
    assert "domain_to_ip" in names
    assert "domain_to_mx" in names
    assert "domain_to_ns" in names
    assert "ip_to_domain" in names
    assert "whois_lookup" in names
    assert len(transforms) == 15


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


def test_list_for_ip_entity(engine: TransformEngine):
    ip = Entity(type=EntityType.IP_ADDRESS, value="1.2.3.4")
    transforms = engine.list_for_entity(ip)
    names = [t.name for t in transforms]
    assert "ip_to_domain" in names
    assert "domain_to_ip" not in names


def test_get_transform(engine: TransformEngine):
    t = engine.get_transform("domain_to_ip")
    assert t is not None
    assert t.display_name == "Domain to IP Address"
    assert t.category == "DNS"


def test_get_nonexistent_transform(engine: TransformEngine):
    assert engine.get_transform("nonexistent") is None


@pytest.mark.asyncio
async def test_run_transform_wrong_type(engine: TransformEngine):
    ip = Entity(type=EntityType.IP_ADDRESS, value="1.2.3.4")
    project = Project(name="test")

    with pytest.raises(ValueError, match="cannot run on"):
        await engine.run_transform("domain_to_ip", ip, project.id)
