from collections import deque
from uuid import UUID

from ogi.models import Entity, Edge


class GraphEngine:
    """In-memory graph with adjacency list for fast traversal."""

    def __init__(self) -> None:
        self._entities: dict[UUID, Entity] = {}
        self._edges: dict[UUID, Edge] = {}
        self._adjacency: dict[UUID, set[UUID]] = {}  # entity_id -> set of edge_ids
        self._neighbors: dict[UUID, set[UUID]] = {}  # entity_id -> set of neighbor entity_ids
        self._hydrated: bool = False

    @property
    def entities(self) -> dict[UUID, Entity]:
        return self._entities

    @property
    def edges(self) -> dict[UUID, Edge]:
        return self._edges

    @property
    def is_hydrated(self) -> bool:
        return self._hydrated

    def mark_hydrated(self) -> None:
        self._hydrated = True

    def mark_stale(self) -> None:
        self._hydrated = False

    def add_entity(self, entity: Entity) -> None:
        self._entities[entity.id] = entity
        if entity.id not in self._adjacency:
            self._adjacency[entity.id] = set()
        if entity.id not in self._neighbors:
            self._neighbors[entity.id] = set()

    def remove_entity(self, entity_id: UUID) -> Entity | None:
        entity = self._entities.pop(entity_id, None)
        if entity is None:
            return None

        edge_ids = list(self._adjacency.get(entity_id, set()))
        for edge_id in edge_ids:
            self.remove_edge(edge_id)

        self._adjacency.pop(entity_id, None)
        self._neighbors.pop(entity_id, None)
        return entity

    def get_entity(self, entity_id: UUID) -> Entity | None:
        return self._entities.get(entity_id)

    def add_edge(self, edge: Edge) -> None:
        if edge.source_id not in self._entities or edge.target_id not in self._entities:
            raise ValueError("Both source and target entities must exist in the graph")

        self._edges[edge.id] = edge
        self._adjacency[edge.source_id].add(edge.id)
        self._adjacency[edge.target_id].add(edge.id)
        self._neighbors[edge.source_id].add(edge.target_id)
        self._neighbors[edge.target_id].add(edge.source_id)

    def remove_edge(self, edge_id: UUID) -> Edge | None:
        edge = self._edges.pop(edge_id, None)
        if edge is None:
            return None

        self._adjacency.get(edge.source_id, set()).discard(edge_id)
        self._adjacency.get(edge.target_id, set()).discard(edge_id)

        # Only remove from neighbors if no other edges connect them
        remaining_edges_src = self._adjacency.get(edge.source_id, set())
        still_connected = False
        for eid in remaining_edges_src:
            e = self._edges.get(eid)
            if e and (e.target_id == edge.target_id or e.source_id == edge.target_id):
                still_connected = True
                break
        if not still_connected:
            self._neighbors.get(edge.source_id, set()).discard(edge.target_id)
            self._neighbors.get(edge.target_id, set()).discard(edge.source_id)

        return edge

    def get_neighbors(self, entity_id: UUID) -> list[Entity]:
        neighbor_ids = self._neighbors.get(entity_id, set())
        return [self._entities[nid] for nid in neighbor_ids if nid in self._entities]

    def get_edges_for_entity(self, entity_id: UUID) -> list[Edge]:
        edge_ids = self._adjacency.get(entity_id, set())
        return [self._edges[eid] for eid in edge_ids if eid in self._edges]

    def find_paths(self, start_id: UUID, end_id: UUID, max_depth: int = 10) -> list[list[UUID]]:
        """BFS-based path finding between two entities."""
        if start_id not in self._entities or end_id not in self._entities:
            return []
        if start_id == end_id:
            return [[start_id]]

        paths: list[list[UUID]] = []
        queue: deque[list[UUID]] = deque([[start_id]])
        visited: set[UUID] = set()

        while queue:
            path = queue.popleft()
            current = path[-1]

            if len(path) > max_depth:
                continue

            if current == end_id:
                paths.append(path)
                continue

            if current in visited:
                continue
            visited.add(current)

            for neighbor_id in self._neighbors.get(current, set()):
                if neighbor_id not in visited:
                    queue.append([*path, neighbor_id])

        return paths

    def get_subgraph(self, entity_ids: set[UUID]) -> tuple[list[Entity], list[Edge]]:
        """Get a subgraph containing only the specified entities and edges between them."""
        entities = [self._entities[eid] for eid in entity_ids if eid in self._entities]
        edges = [
            e for e in self._edges.values()
            if e.source_id in entity_ids and e.target_id in entity_ids
        ]
        return entities, edges

    def merge_entities(self, keep_id: UUID, merge_id: UUID) -> Entity | None:
        """Merge merge_id entity into keep_id, reassigning edges."""
        keep = self._entities.get(keep_id)
        merge = self._entities.get(merge_id)
        if keep is None or merge is None:
            return None

        # Reassign edges from merge to keep
        edge_ids = list(self._adjacency.get(merge_id, set()))
        for edge_id in edge_ids:
            edge = self._edges.get(edge_id)
            if edge is None:
                continue
            self.remove_edge(edge_id)
            new_source = keep_id if edge.source_id == merge_id else edge.source_id
            new_target = keep_id if edge.target_id == merge_id else edge.target_id
            if new_source == new_target:
                continue  # skip self-loops
            new_edge = edge.model_copy(update={"source_id": new_source, "target_id": new_target})
            self.add_edge(new_edge)

        # Merge properties
        merged_props = {**merge.properties, **keep.properties}
        keep_updated = keep.model_copy(update={"properties": merged_props})
        self._entities[keep_id] = keep_updated

        self.remove_entity(merge_id)
        return keep_updated

    def clear(self) -> None:
        self._entities.clear()
        self._edges.clear()
        self._adjacency.clear()
        self._neighbors.clear()
        self._hydrated = False
