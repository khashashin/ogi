import json
from datetime import datetime
from uuid import UUID

import aiosqlite

from ogi.models import Edge, EdgeCreate, EdgeUpdate


class EdgeStore:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def create(self, project_id: UUID, data: EdgeCreate) -> Edge:
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
        await self.db.execute(
            """INSERT INTO edges
               (id, project_id, source_id, target_id, label, weight, properties, bidirectional, source_transform, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(edge.id),
                str(project_id),
                str(edge.source_id),
                str(edge.target_id),
                edge.label,
                edge.weight,
                json.dumps(edge.properties),
                int(edge.bidirectional),
                edge.source_transform,
                edge.created_at.isoformat(),
            ),
        )
        await self.db.commit()
        return edge

    async def get(self, edge_id: UUID) -> Edge | None:
        cursor = await self.db.execute(
            "SELECT * FROM edges WHERE id = ?", (str(edge_id),)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_edge(row)

    async def list_by_project(self, project_id: UUID) -> list[Edge]:
        cursor = await self.db.execute(
            "SELECT * FROM edges WHERE project_id = ? ORDER BY created_at",
            (str(project_id),),
        )
        rows = await cursor.fetchall()
        return [self._row_to_edge(row) for row in rows]

    async def update(self, edge_id: UUID, data: EdgeUpdate) -> Edge | None:
        edge = await self.get(edge_id)
        if edge is None:
            return None

        updates: list[str] = []
        params: list[str | int] = []

        if data.label is not None:
            updates.append("label = ?")
            params.append(data.label)
        if data.weight is not None:
            updates.append("weight = ?")
            params.append(data.weight)
        if data.properties is not None:
            updates.append("properties = ?")
            params.append(json.dumps(data.properties))

        if not updates:
            return edge

        params.append(str(edge_id))
        await self.db.execute(
            f"UPDATE edges SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        await self.db.commit()
        return await self.get(edge_id)

    async def delete(self, edge_id: UUID) -> bool:
        cursor = await self.db.execute(
            "DELETE FROM edges WHERE id = ?", (str(edge_id),)
        )
        await self.db.commit()
        return cursor.rowcount > 0

    def _row_to_edge(self, row: aiosqlite.Row) -> Edge:
        return Edge(
            id=UUID(row["id"]),
            project_id=UUID(row["project_id"]),
            source_id=UUID(row["source_id"]),
            target_id=UUID(row["target_id"]),
            label=row["label"],
            weight=row["weight"],
            properties=json.loads(row["properties"]),
            bidirectional=bool(row["bidirectional"]),
            source_transform=row["source_transform"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
