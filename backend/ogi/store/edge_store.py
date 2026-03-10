from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from ogi.models import Edge, EdgeCreate, EdgeUpdate


class EdgeStore:
    """Edge CRUD – unified implementation using SQLModel and AsyncSession."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_existing(
        self, project_id: UUID, source_id: UUID, target_id: UUID, label: str
    ) -> Edge | None:
        """Check if an edge with the same source, target, and label already exists."""
        stmt = select(Edge).where(
            Edge.project_id == project_id,
            Edge.source_id == source_id,
            Edge.target_id == target_id,
            Edge.label == label,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, project_id: UUID, data: EdgeCreate) -> Edge:
        # Deduplicate: skip if an identical edge already exists
        existing = await self.find_existing(
            project_id, data.source_id, data.target_id, data.label
        )
        if existing is not None:
            return existing

        edge = Edge(
            source_id=data.source_id,
            target_id=data.target_id,
            label=data.label,
            weight=data.weight,
            properties=data.properties,
            bidirectional=data.bidirectional,
            source_transform=data.source_transform,
            project_id=project_id,
        )
        self.session.add(edge)
        await self.session.commit()
        await self.session.refresh(edge)
        return edge

    async def get(self, edge_id: UUID) -> Edge | None:
        return await self.session.get(Edge, edge_id)

    async def list_by_project(self, project_id: UUID) -> list[Edge]:
        stmt = select(Edge).where(Edge.project_id == project_id).order_by(Edge.created_at)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, edge_id: UUID, data: EdgeUpdate) -> Edge | None:
        edge = await self.get(edge_id)
        if edge is None:
            return None

        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return edge

        for key, value in update_data.items():
            setattr(edge, key, value)
            
        self.session.add(edge)
        await self.session.commit()
        await self.session.refresh(edge)
        return edge

    async def delete(self, edge_id: UUID) -> bool:
        edge = await self.get(edge_id)
        if not edge:
            return False
            
        await self.session.delete(edge)
        await self.session.commit()
        return True
