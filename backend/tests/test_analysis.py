"""Tests for graph analysis algorithms."""
import pytest

from ogi.models import Entity, Edge, EntityType
from ogi.engine.graph_engine import GraphEngine
from ogi.engine import analysis


@pytest.fixture
def empty_engine() -> GraphEngine:
    return GraphEngine()


@pytest.fixture
def triangle_engine() -> GraphEngine:
    """Three entities connected in a triangle."""
    engine = GraphEngine()
    a = Entity(type=EntityType.DOMAIN, value="a.com")
    b = Entity(type=EntityType.DOMAIN, value="b.com")
    c = Entity(type=EntityType.DOMAIN, value="c.com")
    engine.add_entity(a)
    engine.add_entity(b)
    engine.add_entity(c)
    engine.add_edge(Edge(source_id=a.id, target_id=b.id, label="link"))
    engine.add_edge(Edge(source_id=b.id, target_id=c.id, label="link"))
    engine.add_edge(Edge(source_id=a.id, target_id=c.id, label="link"))
    return engine


@pytest.fixture
def disconnected_engine() -> GraphEngine:
    """Two pairs of connected entities, not connected to each other."""
    engine = GraphEngine()
    a = Entity(type=EntityType.DOMAIN, value="a.com")
    b = Entity(type=EntityType.DOMAIN, value="b.com")
    c = Entity(type=EntityType.IP_ADDRESS, value="1.1.1.1")
    d = Entity(type=EntityType.IP_ADDRESS, value="2.2.2.2")
    engine.add_entity(a)
    engine.add_entity(b)
    engine.add_entity(c)
    engine.add_entity(d)
    engine.add_edge(Edge(source_id=a.id, target_id=b.id, label="link"))
    engine.add_edge(Edge(source_id=c.id, target_id=d.id, label="link"))
    return engine


def test_degree_centrality_empty(empty_engine: GraphEngine):
    result = analysis.degree_centrality(empty_engine)
    assert result == {}


def test_degree_centrality_triangle(triangle_engine: GraphEngine):
    result = analysis.degree_centrality(triangle_engine)
    assert len(result) == 3
    # In a triangle, every node has degree 2, so centrality = 2/(3-1) = 1.0
    for score in result.values():
        assert score == pytest.approx(1.0)


def test_betweenness_centrality_triangle(triangle_engine: GraphEngine):
    result = analysis.betweenness_centrality(triangle_engine)
    assert len(result) == 3
    # In a triangle, no node is on a shortest path between any other pair
    for score in result.values():
        assert score == pytest.approx(0.0)


def test_closeness_centrality_triangle(triangle_engine: GraphEngine):
    result = analysis.closeness_centrality(triangle_engine)
    assert len(result) == 3
    # In a triangle, every node has distance 1 to both others, so closeness = 2/2 = 1.0
    for score in result.values():
        assert score == pytest.approx(1.0)


def test_pagerank_triangle(triangle_engine: GraphEngine):
    result = analysis.pagerank(triangle_engine)
    assert len(result) == 3
    # In a symmetric triangle, all scores should be equal
    scores = list(result.values())
    assert scores[0] == pytest.approx(scores[1], abs=1e-6)
    assert scores[1] == pytest.approx(scores[2], abs=1e-6)


def test_pagerank_empty(empty_engine: GraphEngine):
    result = analysis.pagerank(empty_engine)
    assert result == {}


def test_connected_components_triangle(triangle_engine: GraphEngine):
    result = analysis.connected_components(triangle_engine)
    assert len(result) == 1
    assert len(result[0]) == 3


def test_connected_components_disconnected(disconnected_engine: GraphEngine):
    result = analysis.connected_components(disconnected_engine)
    assert len(result) == 2
    sizes = sorted([len(c) for c in result])
    assert sizes == [2, 2]


def test_graph_stats(triangle_engine: GraphEngine):
    result = analysis.graph_stats(triangle_engine)
    assert result["entity_count"] == 3
    assert result["edge_count"] == 3
    assert result["connected_components"] == 1
    assert result["avg_degree"] == 2.0
    assert result["density"] > 0
