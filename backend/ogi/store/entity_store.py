import json
from datetime import datetime, timezone
from uuid import UUID

import aiosqlite

from ogi.models import Entity, EntityCreate, EntityUpdate, EntityType


class EntityStore:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def find_by_type_and_value(
        self, project_id: UUID, entity_type: EntityType, value: str
    ) -> Entity | None:
        """Find an existing entity by type + value within a project."""
        cursor = await self.db.execute(
            "SELECT * FROM entities WHERE project_id = ? AND type = ? AND value = ?",
            (str(project_id), entity_type.value, value),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_entity(row)

    async def create(self, project_id: UUID, data: EntityCreate) -> Entity:
        # Deduplicate: if same type+value already exists, return the existing entity
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
        """Persist a transform-produced entity. Deduplicates by type+value,
        returning the existing entity (and its ID) if one already exists."""
        existing = await self.find_by_type_and_value(project_id, entity.type, entity.value)
        if existing is not None:
            return existing

        entity.project_id = project_id
        await self._insert(project_id, entity)
        return entity

    async def _insert(self, project_id: UUID, entity: Entity) -> None:
        await self.db.execute(
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
        await self.db.commit()

    async def get(self, entity_id: UUID) -> Entity | None:
        cursor = await self.db.execute(
            "SELECT * FROM entities WHERE id = ?", (str(entity_id),)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_entity(row)

    async def list_by_project(self, project_id: UUID) -> list[Entity]:
        cursor = await self.db.execute(
            "SELECT * FROM entities WHERE project_id = ? ORDER BY created_at",
            (str(project_id),),
        )
        rows = await cursor.fetchall()
        return [self._row_to_entity(row) for row in rows]

    async def update(self, entity_id: UUID, data: EntityUpdate) -> Entity | None:
        entity = await self.get(entity_id)
        if entity is None:
            return None

        updates: list[str] = []
        params: list[str | int] = []

        if data.value is not None:
            updates.append("value = ?")
            params.append(data.value)
        if data.properties is not None:
            updates.append("properties = ?")
            params.append(json.dumps(data.properties))
        if data.weight is not None:
            updates.append("weight = ?")
            params.append(data.weight)
        if data.notes is not None:
            updates.append("notes = ?")
            params.append(data.notes)
        if data.tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(data.tags))

        if not updates:
            return entity

        now = datetime.now(timezone.utc).isoformat()
        updates.append("updated_at = ?")
        params.append(now)
        params.append(str(entity_id))

        await self.db.execute(
            f"UPDATE entities SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        await self.db.commit()
        return await self.get(entity_id)

    async def delete(self, entity_id: UUID) -> bool:
        cursor = await self.db.execute(
            "DELETE FROM entities WHERE id = ?", (str(entity_id),)
        )
        await self.db.commit()
        return cursor.rowcount > 0

    def _row_to_entity(self, row: aiosqlite.Row) -> Entity:
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
