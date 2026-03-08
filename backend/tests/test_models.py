from uuid import UUID

from ogi.models import (
    Entity, EntityCreate, EntityType,
    Edge, EdgeCreate,
    Project, ProjectCreate,
    TransformResult, TransformRun, TransformStatus,
)


def test_entity_creation():
    entity = Entity(type=EntityType.DOMAIN, value="example.com")
    assert isinstance(entity.id, UUID)
    assert entity.type == EntityType.DOMAIN
    assert entity.value == "example.com"
    assert entity.icon == "globe"  # auto-assigned from meta
    assert entity.weight == 1
    assert entity.source == "manual"
    assert entity.origin_source == "manual"


def test_entity_create_schema():
    data = EntityCreate(type=EntityType.IP_ADDRESS, value="1.2.3.4")
    assert data.type == EntityType.IP_ADDRESS
    assert data.value == "1.2.3.4"
    assert data.properties == {}
    assert data.origin_source is None


def test_edge_creation():
    e1 = Entity(type=EntityType.DOMAIN, value="a.com")
    e2 = Entity(type=EntityType.IP_ADDRESS, value="1.2.3.4")
    edge = Edge(source_id=e1.id, target_id=e2.id, label="resolves")
    assert isinstance(edge.id, UUID)
    assert edge.source_id == e1.id
    assert edge.target_id == e2.id
    assert edge.label == "resolves"


def test_project_creation():
    project = Project(name="Test Project", description="desc")
    assert isinstance(project.id, UUID)
    assert project.name == "Test Project"


def test_transform_result():
    entity = Entity(type=EntityType.IP_ADDRESS, value="1.2.3.4")
    result = TransformResult(entities=[entity], messages=["found 1 IP"])
    assert len(result.entities) == 1
    assert result.messages == ["found 1 IP"]


def test_transform_run():
    run = TransformRun(
        project_id=Project(name="p").id,
        transform_name="test",
        input_entity_id=Entity(type=EntityType.DOMAIN, value="x.com").id,
    )
    assert run.status == TransformStatus.PENDING
    assert run.result is None


def test_entity_types():
    names = {item.value for item in EntityType}
    assert "Person" in names
    assert "Username" in names
    assert len(names) == len(EntityType)
