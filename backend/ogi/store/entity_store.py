from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

import aiosqlite

from ogi.models import Entity, EntityCreate, EntityUpdate, EntityType


class EntityStore:
    """Entity CRUD – works with either aiosqlite.Connection or asyncpg.Pool."""

    def __init__(self, db: object) -> None:
        self.db = db
        self._is_sqlite = isinstance(db, aiosqlite.Connection)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def find_by_type_and_value(
        self, project_id: UUID, entity_type: EntityType, value: str
    ) -> Entity | None:
        if self._is_sqlite:
            return await self._sqlite_find(project_id, entity_type, value)
        return await self._pg_find(project_id, entity_type, value)

    async def create(self, project_id: UUID, data: EntityCreate) -> Entity:
        existing = await self.find_by_type_and_value(project_id, data.type, data.value)
        if existing is not None:
            return existing

        entity = Entity(
            type=data.type,
            value=data.value,
            properties=data.properties,
            weight=data.weight,
            notes=data.notes,
            tags=data.tags,
            source=data.source,
            project_id=project_id,
        )
        await self._insert(project_id, entity)
        return entity

    async def save(self, project_id: UUID, entity: Entity) -> Entity:
        existing = await self.find_by_type_and_value(project_id, entity.type, entity.value)
        if existing is not None:
            return existing
        entity.project_id = project_id
        await self._insert(project_id, entity)
        return entity

    async def get(self, entity_id: UUID) -> Entity | None:
        if self._is_sqlite:
            return await self._sqlite_get(entity_id)
        return await self._pg_get(entity_id)

    async def list_by_project(self, project_id: UUID) -> list[Entity]:
        if self._is_sqlite:
            return await self._sqlite_list(project_id)
        return await self._pg_list(project_id)

    async def update(self, entity_id: UUID, data: EntityUpdate) -> Entity | None:
        entity = await self.get(entity_id)
        if entity is None:
            return None

        fields: dict[str, object] = {}
        if data.value is not None:
            fields["value"] = data.value
        if data.properties is not None:
            fields["properties"] = data.properties
        if data.weight is not None:
            fields["weight"] = data.weight
        if data.notes is not None:
            fields["notes"] = data.notes
        if data.tags is not None:
            fields["tags"] = data.tags
        if not fields:
            return entity

        now = datetime.now(timezone.utc)
        if self._is_sqlite:
            await self._sqlite_update(entity_id, fields, now)
        else:
            await self._pg_update(entity_id, fields, now)
        return await self.get(entity_id)

    async def delete(self, entity_id: UUID) -> bool:
        if self._is_sqlite:
            return await self._sqlite_delete(entity_id)
        return await self._pg_delete(entity_id)

    # ------------------------------------------------------------------
    # Internal insert
    # ------------------------------------------------------------------

    async def _insert(self, project_id: UUID, entity: Entity) -> None:
        if self._is_sqlite:
            await self._sqlite_insert(project_id, entity)
        else:
            await self._pg_insert(project_id, entity)

    # ------------------------------------------------------------------
    # SQLite implementation
    # ------------------------------------------------------------------

    async def _sqlite_find(self, project_id: UUID, entity_type: EntityType, value: str) -> Entity | None:
        db: aiosqlite.Connection = self.db  # type: ignore[assignment]
        cursor = await db.execute(
            "SELECT * FROM entities WHERE project_id = ? AND type = ? AND value = ?",
            (str(project_id), entity_type.value, value),
        )
        row = await cursor.fetchone()
        return self._sqlite_row(row) if row else None

    async def _sqlite_insert(self, project_id: UUID, entity: Entity) -> None:
        db: aiosqlite.Connection = self.db  # type: ignore[assignment]
        await db.execute(
            """INSERT INTO entities
               (id, project_id, type, value, properties, icon, weight, notes, tags, source, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(entity.id),
                str(project_id),
                entity.type.value,
                entity.value,
                json.dumps(entity.properties),
                entity.icon,
                entity.weight,
                entity.notes,
                json.dumps(entity.tags),
                entity.source,
                entity.created_at.isoformat(),
                entity.updated_at.isoformat(),
            ),
        )
        await db.commit()

    async def _sqlite_get(self, entity_id: UUID) -> Entity | None:
        db: aiosqlite.Connection = self.db  # type: ignore[assignment]
        cursor = await db.execute("SELECT * FROM entities WHERE id = ?", (str(entity_id),))
        row = await cursor.fetchone()
        return self._sqlite_row(row) if row else None

    async def _sqlite_list(self, project_id: UUID) -> list[Entity]:
        db: aiosqlite.Connection = self.db  # type: ignore[assignment]
        cursor = await db.execute(
            "SELECT * FROM entities WHERE project_id = ? ORDER BY created_at",
            (str(project_id),),
        )
        rows = await cursor.fetchall()
        return [self._sqlite_row(row) for row in rows]

    async def _sqlite_update(self, entity_id: UUID, fields: dict[str, object], now: datetime) -> None:
        db: aiosqlite.Connection = self.db  # type: ignore[assignment]
        updates: list[str] = []
        params: list[object] = []
        for k, v in fields.items():
            updates.append(f"{k} = ?")
            if k in ("properties", "tags"):
                params.append(json.dumps(v))
            else:
                params.append(v)
        updates.append("updated_at = ?")
        params.append(now.isoformat())
        params.append(str(entity_id))
        await db.execute(f"UPDATE entities SET {', '.join(updates)} WHERE id = ?", params)
        await db.commit()

    async def _sqlite_delete(self, entity_id: UUID) -> bool:
        db: aiosqlite.Connection = self.db  # type: ignore[assignment]
        cursor = await db.execute("DELETE FROM entities WHERE id = ?", (str(entity_id),))
        await db.commit()
        return cursor.rowcount > 0

    @staticmethod
    def _sqlite_row(row: aiosqlite.Row) -> Entity:
        return Entity(
            id=UUID(row["id"]),
            project_id=UUID(row["project_id"]),
            type=EntityType(row["type"]),
            value=row["value"],
            properties=json.loads(row["properties"]),
            icon=row["icon"],
            weight=row["weight"],
            notes=row["notes"],
            tags=json.loads(row["tags"]),
            source=row["source"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # ------------------------------------------------------------------
    # PostgreSQL implementation
    # ------------------------------------------------------------------

    async def _pg_find(self, project_id: UUID, entity_type: EntityType, value: str) -> Entity | None:
        pool = self.db
        row = await pool.fetchrow(  # type: ignore[union-attr]
            "SELECT * FROM entities WHERE project_id = $1 AND type = $2 AND value = $3",
            project_id, entity_type.value, value,
        )
        return self._pg_row(row) if row else None

    async def _pg_insert(self, project_id: UUID, entity: Entity) -> None:
        pool = self.db
        await pool.execute(  # type: ignore[union-attr]
            """INSERT INTO entities
               (id, project_id, type, value, properties, icon, weight, notes, tags, source, created_at, updated_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)""",
            entity.id,
            project_id,
            entity.type.value,
            entity.value,
            json.dumps(entity.properties),
            entity.icon,
            entity.weight,
            entity.notes,
            json.dumps(entity.tags),
            entity.source,
            entity.created_at,
            entity.updated_at,
        )

    async def _pg_get(self, entity_id: UUID) -> Entity | None:
        pool = self.db
        row = await pool.fetchrow("SELECT * FROM entities WHERE id = $1", entity_id)  # type: ignore[union-attr]
        return self._pg_row(row) if row else None

    async def _pg_list(self, project_id: UUID) -> list[Entity]:
        pool = self.db
        rows = await pool.fetch(  # type: ignore[union-attr]
            "SELECT * FROM entities WHERE project_id = $1 ORDER BY created_at", project_id,
        )
        return [self._pg_row(row) for row in rows]

    async def _pg_update(self, entity_id: UUID, fields: dict[str, object], now: datetime) -> None:
        pool = self.db
        set_clauses: list[str] = []
        params: list[object] = []
        idx = 1
        for k, v in fields.items():
            set_clauses.append(f"{k} = ${idx}")
            if k in ("properties", "tags"):
                params.append(json.dumps(v))
            else:
                params.append(v)
            idx += 1
        set_clauses.append(f"updated_at = ${idx}")
        params.append(now)
        idx += 1
        params.append(entity_id)
        await pool.execute(  # type: ignore[union-attr]
            f"UPDATE entities SET {', '.join(set_clauses)} WHERE id = ${idx}",
            *params,
        )

    async def _pg_delete(self, entity_id: UUID) -> bool:
        pool = self.db
        result = await pool.execute("DELETE FROM entities WHERE id = $1", entity_id)  # type: ignore[union-attr]
        return result == "DELETE 1"

    @staticmethod
    def _pg_row(row: object) -> Entity:
        r = row  # asyncpg.Record
        tags = r["tags"]  # type: ignore[index]
        if isinstance(tags, str):
            tags = json.loads(tags)
        props = r["properties"]  # type: ignore[index]
        if isinstance(props, str):
            props = json.loads(props)
        return Entity(
            id=r["id"],  # type: ignore[index]
            project_id=r["project_id"],  # type: ignore[index]
            type=EntityType(r["type"]),  # type: ignore[index]
            value=r["value"],  # type: ignore[index]
            properties=props,
            icon=r["icon"],  # type: ignore[index]
            weight=r["weight"],  # type: ignore[index]
            notes=r["notes"],  # type: ignore[index]
            tags=tags,
            source=r["source"],  # type: ignore[index]
            created_at=r["created_at"],  # type: ignore[index]
            updated_at=r["updated_at"],  # type: ignore[index]
        )
