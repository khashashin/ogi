from uuid import UUID

from pydantic import BaseModel, Field

from .entity import Entity
from .edge import Edge


class Graph(BaseModel):
    project_id: UUID
    entities: dict[str, Entity] = Field(default_factory=dict)
    edges: dict[str, Edge] = Field(default_factory=dict)

    @property
    def entity_count(self) -> int:
        return len(self.entities)

    @property
    def edge_count(self) -> int:
        return len(self.edges)
