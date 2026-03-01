from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

import aiosqlite

from ogi.models import Edge, EdgeCreate, EdgeUpdate


class EdgeStore:
    """Edge CRUD – works with either aiosqlite.Connection or asyncpg.Pool."""

    def __init__(self, db: object) -> None:
        self.db = db
        self._is_sqlite = isinstance(db, aiosqlite.Connection)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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
        if self._is_sqlite:
            await self._sqlite_insert(project_id, edge)
        else:
            await self._pg_insert(project_id, edge)
        return edge

    async def get(self, edge_id: UUID) -> Edge | None:
        if self._is_sqlite:
            return await self._sqlite_get(edge_id)
        return await self._pg_get(edge_id)

    async def list_by_project(self, project_id: UUID) -> list[Edge]:
        if self._is_sqlite:
            return await self._sqlite_list(project_id)
        return await self._pg_list(project_id)

    async def update(self, edge_id: UUID, data: EdgeUpdate) -> Edge | None:
        edge = await self.get(edge_id)
        if edge is None:
            return None

        fields: dict[str, object] = {}
        if data.label is not None:
            fields["label"] = data.label
        if data.weight is not None:
            fields["weight"] = data.weight
        if data.properties is not None:
            fields["properties"] = data.properties
        if not fields:
            return edge

        if self._is_sqlite:
            await self._sqlite_update(edge_id, fields)
        else:
            await self._pg_update(edge_id, fields)
        return await self.get(edge_id)

    async def delete(self, edge_id: UUID) -> bool:
        if self._is_sqlite:
            return await self._sqlite_delete(edge_id)
        return await self._pg_delete(edge_id)

    # ------------------------------------------------------------------
    # SQLite implementation
    # ------------------------------------------------------------------

    async def _sqlite_insert(self, project_id: UUID, edge: Edge) -> None:
        db: aiosqlite.Connection = self.db  # type: ignore[assignment]
        await db.execute(
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
        await db.commit()

    async def _sqlite_get(self, edge_id: UUID) -> Edge | None:
        db: aiosqlite.Connection = self.db  # type: ignore[assignment]
        cursor = await db.execute("SELECT * FROM edges WHERE id = ?", (str(edge_id),))
        row = await cursor.fetchone()
        return self._sqlite_row(row) if row else None

    async def _sqlite_list(self, project_id: UUID) -> list[Edge]:
        db: aiosqlite.Connection = self.db  # type: ignore[assignment]
        cursor = await db.execute(
            "SELECT * FROM edges WHERE project_id = ? ORDER BY created_at",
            (str(project_id),),
        )
        rows = await cursor.fetchall()
        return [self._sqlite_row(row) for row in rows]

    async def _sqlite_update(self, edge_id: UUID, fields: dict[str, object]) -> None:
        db: aiosqlite.Connection = self.db  # type: ignore[assignment]
        updates: list[str] = []
        params: list[object] = []
        for k, v in fields.items():
            updates.append(f"{k} = ?")
            if k == "properties":
                params.append(json.dumps(v))
            else:
                params.append(v)
        params.append(str(edge_id))
        await db.execute(f"UPDATE edges SET {', '.join(updates)} WHERE id = ?", params)
        await db.commit()

    async def _sqlite_delete(self, edge_id: UUID) -> bool:
        db: aiosqlite.Connection = self.db  # type: ignore[assignment]
        cursor = await db.execute("DELETE FROM edges WHERE id = ?", (str(edge_id),))
        await db.commit()
        return cursor.rowcount > 0

    @staticmethod
    def _sqlite_row(row: aiosqlite.Row) -> Edge:
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

    # ------------------------------------------------------------------
    # PostgreSQL implementation
    # ------------------------------------------------------------------

    async def _pg_insert(self, project_id: UUID, edge: Edge) -> None:
        pool = self.db
        await pool.execute(  # type: ignore[union-attr]
            """INSERT INTO edges
               (id, project_id, source_id, target_id, label, weight, properties, bidirectional, source_transform, created_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
            edge.id,
            project_id,
            edge.source_id,
            edge.target_id,
            edge.label,
            edge.weight,
            json.dumps(edge.properties),
            edge.bidirectional,
            edge.source_transform,
            edge.created_at,
        )

    async def _pg_get(self, edge_id: UUID) -> Edge | None:
        pool = self.db
        row = await pool.fetchrow("SELECT * FROM edges WHERE id = $1", edge_id)  # type: ignore[union-attr]
        return self._pg_row(row) if row else None

    async def _pg_list(self, project_id: UUID) -> list[Edge]:
        pool = self.db
        rows = await pool.fetch(  # type: ignore[union-attr]
            "SELECT * FROM edges WHERE project_id = $1 ORDER BY created_at", project_id,
        )
        return [self._pg_row(row) for row in rows]

    async def _pg_update(self, edge_id: UUID, fields: dict[str, object]) -> None:
        pool = self.db
        set_clauses: list[str] = []
        params: list[object] = []
        idx = 1
        for k, v in fields.items():
            set_clauses.append(f"{k} = ${idx}")
            if k == "properties":
                params.append(json.dumps(v))
            else:
                params.append(v)
            idx += 1
        params.append(edge_id)
        await pool.execute(  # type: ignore[union-attr]
            f"UPDATE edges SET {', '.join(set_clauses)} WHERE id = ${idx}",
            *params,
        )

    async def _pg_delete(self, edge_id: UUID) -> bool:
        pool = self.db
        result = await pool.execute("DELETE FROM edges WHERE id = $1", edge_id)  # type: ignore[union-attr]
        return result == "DELETE 1"

    @staticmethod
    def _pg_row(row: object) -> Edge:
        r = row
        props = r["properties"]  # type: ignore[index]
        if isinstance(props, str):
            props = json.loads(props)
        return Edge(
            id=r["id"],  # type: ignore[index]
            project_id=r["project_id"],  # type: ignore[index]
            source_id=r["source_id"],  # type: ignore[index]
            target_id=r["target_id"],  # type: ignore[index]
            label=r["label"],  # type: ignore[index]
            weight=r["weight"],  # type: ignore[index]
            properties=props,
            bidirectional=bool(r["bidirectional"]),  # type: ignore[index]
            source_transform=r["source_transform"],  # type: ignore[index]
            created_at=r["created_at"],  # type: ignore[index]
        )
