import pytest
from uuid import uuid4

from ogi.models import Entity, EntityType, Edge
from ogi.engine.graph_engine import GraphEngine


@pytest.fixture
def engine():
    return GraphEngine()


@pytest.fixture
def sample_entities():
    return [
        Entity(type=EntityType.DOMAIN, value="example.com"),
        Entity(type=EntityType.IP_ADDRESS, value="93.184.216.34"),
        Entity(type=EntityType.IP_ADDRESS, value="2606:2800:220:1::"),
    ]


def test_add_entity(engine: GraphEngine, sample_entities: list[Entity]):
    engine.add_entity(sample_entities[0])
    assert engine.get_entity(sample_entities[0].id) is not None
    assert len(engine.entities) == 1


def test_remove_entity(engine: GraphEngine, sample_entities: list[Entity]):
    engine.add_entity(sample_entities[0])
    removed = engine.remove_entity(sample_entities[0].id)
    assert removed is not None
    assert len(engine.entities) == 0


def test_add_edge(engine: GraphEngine, sample_entities: list[Entity]):
    e1, e2 = sample_entities[0], sample_entities[1]
    engine.add_entity(e1)
    engine.add_entity(e2)

    edge = Edge(source_id=e1.id, target_id=e2.id, label="resolves to")
    engine.add_edge(edge)

    assert len(engine.edges) == 1
    neighbors = engine.get_neighbors(e1.id)
    assert len(neighbors) == 1
    assert neighbors[0].id == e2.id


def test_add_edge_missing_entity(engine: GraphEngine, sample_entities: list[Entity]):
    engine.add_entity(sample_entities[0])
    edge = Edge(source_id=sample_entities[0].id, target_id=uuid4(), label="x")
    with pytest.raises(ValueError):
        engine.add_edge(edge)


def test_remove_edge(engine: GraphEngine, sample_entities: list[Entity]):
    e1, e2 = sample_entities[0], sample_entities[1]
    engine.add_entity(e1)
    engine.add_entity(e2)
    edge = Edge(source_id=e1.id, target_id=e2.id, label="test")
    engine.add_edge(edge)

    removed = engine.remove_edge(edge.id)
    assert removed is not None
    assert len(engine.edges) == 0
    assert len(engine.get_neighbors(e1.id)) == 0


def test_find_paths(engine: GraphEngine, sample_entities: list[Entity]):
    e1, e2, e3 = sample_entities
    for e in sample_entities:
        engine.add_entity(e)

    engine.add_edge(Edge(source_id=e1.id, target_id=e2.id, label="a"))
    engine.add_edge(Edge(source_id=e2.id, target_id=e3.id, label="b"))

    paths = engine.find_paths(e1.id, e3.id)
    assert len(paths) >= 1
    assert paths[0] == [e1.id, e2.id, e3.id]


def test_get_subgraph(engine: GraphEngine, sample_entities: list[Entity]):
    e1, e2, e3 = sample_entities
    for e in sample_entities:
        engine.add_entity(e)

    engine.add_edge(Edge(source_id=e1.id, target_id=e2.id, label="a"))
    engine.add_edge(Edge(source_id=e2.id, target_id=e3.id, label="b"))

    entities, edges = engine.get_subgraph({e1.id, e2.id})
    assert len(entities) == 2
    assert len(edges) == 1  # only the edge between e1 and e2


def test_merge_entities(engine: GraphEngine, sample_entities: list[Entity]):
    e1, e2, e3 = sample_entities
    for e in sample_entities:
        engine.add_entity(e)

    engine.add_edge(Edge(source_id=e1.id, target_id=e2.id, label="a"))
    engine.add_edge(Edge(source_id=e1.id, target_id=e3.id, label="b"))

    merged = engine.merge_entities(e2.id, e3.id)
    assert merged is not None
    assert e3.id not in engine.entities
    assert len(engine.entities) == 2


def test_clear(engine: GraphEngine, sample_entities: list[Entity]):
    for e in sample_entities:
        engine.add_entity(e)
    engine.clear()
    assert len(engine.entities) == 0
    assert len(engine.edges) == 0
