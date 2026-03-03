"""Graph analysis algorithms operating on the in-memory GraphEngine."""
from collections import deque
from uuid import UUID

from ogi.engine.graph_engine import GraphEngine


def degree_centrality(engine: GraphEngine) -> dict[UUID, float]:
    """Node degree / (n-1) for each entity."""
    n = len(engine.entities)
    if n <= 1:
        return {eid: 0.0 for eid in engine.entities}
    return {
        eid: len(engine._adjacency.get(eid, set())) / (n - 1)
        for eid in engine.entities
    }


def betweenness_centrality(engine: GraphEngine) -> dict[UUID, float]:
    """Brandes' algorithm for betweenness centrality."""
    scores: dict[UUID, float] = {eid: 0.0 for eid in engine.entities}
    nodes = list(engine.entities.keys())

    for s in nodes:
        # BFS from s
        stack: list[UUID] = []
        pred: dict[UUID, list[UUID]] = {v: [] for v in nodes}
        sigma: dict[UUID, float] = {v: 0.0 for v in nodes}
        sigma[s] = 1.0
        dist: dict[UUID, int] = {v: -1 for v in nodes}
        dist[s] = 0
        queue: deque[UUID] = deque([s])

        while queue:
            v = queue.popleft()
            stack.append(v)
            for w in engine._neighbors.get(v, set()):
                if dist[w] < 0:
                    dist[w] = dist[v] + 1
                    queue.append(w)
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    pred[w].append(v)

        delta: dict[UUID, float] = {v: 0.0 for v in nodes}
        while stack:
            w = stack.pop()
            for v in pred[w]:
                delta[v] += (sigma[v] / sigma[w]) * (1.0 + delta[w])
            if w != s:
                scores[w] += delta[w]

    # Normalize for undirected graph
    n = len(nodes)
    if n > 2:
        norm = 2.0 / ((n - 1) * (n - 2))
        scores = {k: v * norm for k, v in scores.items()}

    return scores


def closeness_centrality(engine: GraphEngine) -> dict[UUID, float]:
    """Inverse of average shortest path length to all other nodes."""
    nodes = list(engine.entities.keys())
    n = len(nodes)
    result: dict[UUID, float] = {}

    for s in nodes:
        # BFS
        dist: dict[UUID, int] = {s: 0}
        queue: deque[UUID] = deque([s])
        while queue:
            v = queue.popleft()
            for w in engine._neighbors.get(v, set()):
                if w not in dist:
                    dist[w] = dist[v] + 1
                    queue.append(w)

        reachable = len(dist) - 1
        if reachable == 0:
            result[s] = 0.0
        else:
            total_dist = sum(dist.values())
            result[s] = reachable / total_dist if total_dist > 0 else 0.0

    return result


def pagerank(
    engine: GraphEngine, damping: float = 0.85, iterations: int = 100
) -> dict[UUID, float]:
    """PageRank algorithm."""
    nodes = list(engine.entities.keys())
    n = len(nodes)
    if n == 0:
        return {}

    scores: dict[UUID, float] = {eid: 1.0 / n for eid in nodes}

    for _ in range(iterations):
        new_scores: dict[UUID, float] = {}
        for node in nodes:
            rank_sum = 0.0
            for neighbor in engine._neighbors.get(node, set()):
                out_degree = len(engine._neighbors.get(neighbor, set()))
                if out_degree > 0:
                    rank_sum += scores[neighbor] / out_degree
            new_scores[node] = (1 - damping) / n + damping * rank_sum
        scores = new_scores

    return scores


def connected_components(engine: GraphEngine) -> list[list[UUID]]:
    """Find connected components."""
    visited: set[UUID] = set()
    components: list[list[UUID]] = []

    for node in engine.entities:
        if node in visited:
            continue
        component: list[UUID] = []
        queue: deque[UUID] = deque([node])
        while queue:
            v = queue.popleft()
            if v in visited:
                continue
            visited.add(v)
            component.append(v)
            for w in engine._neighbors.get(v, set()):
                if w not in visited:
                    queue.append(w)
        components.append(component)

    return components


def graph_stats(engine: GraphEngine) -> dict[str, int | float]:
    """Compute basic graph statistics."""
    n = len(engine.entities)
    m = len(engine.edges)
    max_edges = n * (n - 1) if n > 1 else 1
    density = m / max_edges if max_edges > 0 else 0.0

    degrees = [len(engine._adjacency.get(eid, set())) for eid in engine.entities]
    avg_degree = sum(degrees) / n if n > 0 else 0.0

    components = connected_components(engine)

    return {
        "entity_count": n,
        "edge_count": m,
        "density": round(density, 4),
        "avg_degree": round(avg_degree, 2),
        "connected_components": len(components),
    }
