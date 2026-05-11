from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from ogi.models import Entity, EntityCreate, EntityUpdate, EntityType


class EntityStore:
    """Entity CRUD – unified implementation using SQLModel and AsyncSession."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_by_type_and_value(
        self, project_id: UUID, entity_type: EntityType, value: str
    ) -> Entity | None:
        stmt = select(Entity).where(
            Entity.project_id == project_id,
            Entity.type == entity_type,
            Entity.value == value
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, project_id: UUID, data: EntityCreate) -> Entity:
        existing = await self.find_by_type_and_value(project_id, data.type, data.value)
        if existing is not None:
            return existing
        origin_source = (data.origin_source or data.source or "manual").strip() or "manual"

        entity = Entity(
            type=data.type,
            value=data.value,
            properties=data.properties,
            weight=data.weight,
            notes=data.notes,
            tags=data.tags,
            source=data.source,
            origin_source=origin_source,
            project_id=project_id,
        )
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return entity

    async def save(self, project_id: UUID, entity: Entity) -> Entity:
        existing = await self.find_by_type_and_value(project_id, entity.type, entity.value)
        if existing is not None:
            # Upsert behavior: merge incoming transform data into existing record.
            existing.properties = {**existing.properties, **entity.properties}

            if entity.tags:
                merged_tags = list(dict.fromkeys([*existing.tags, *entity.tags]))
                existing.tags = merged_tags

            if entity.notes:
                existing.notes = entity.notes

            if entity.source:
                existing.source = entity.source

            if not existing.origin_source.strip():
                existing.origin_source = self._origin_source(existing, fallback=entity.source)

            if entity.icon:
                existing.icon = entity.icon

            if entity.weight is not None:
                existing.weight = max(existing.weight, entity.weight)

            existing.updated_at = datetime.now(timezone.utc)
            self.session.add(existing)
            await self.session.commit()
            await self.session.refresh(existing)
            return existing

        entity.project_id = project_id
        entity.origin_source = (entity.origin_source or entity.source or "manual").strip() or "manual"
        # Ensure datetimes are proper objects (not strings from JSON deserialization)
        now = datetime.now(timezone.utc)
        entity.created_at = now
        entity.updated_at = now
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return entity

    async def get(self, entity_id: UUID) -> Entity | None:
        return await self.session.get(Entity, entity_id)

    async def list_by_project(
        self,
        project_id: UUID,
        type_filter: EntityType | None = None,
        limit: int | None = None,
    ) -> list[Entity]:
        stmt = select(Entity).where(Entity.project_id == project_id)
        if type_filter is not None:
            stmt = stmt.where(Entity.type == type_filter)
        stmt = stmt.order_by(Entity.created_at)
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search(
        self,
        project_id: UUID,
        query: str,
        type_filter: EntityType | None = None,
        limit: int = 50,
    ) -> list[Entity]:
        pattern = f"%{query.strip()}%"
        stmt = select(Entity).where(Entity.project_id == project_id)
        if type_filter is not None:
            stmt = stmt.where(Entity.type == type_filter)
        stmt = stmt.where(Entity.value.ilike(pattern)).order_by(Entity.created_at).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, entity_id: UUID, data: EntityUpdate) -> Entity | None:
        entity = await self.get(entity_id)
        if entity is None:
            return None

        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return entity

        for key, value in update_data.items():
            setattr(entity, key, value)
            
        entity.updated_at = datetime.now(timezone.utc)
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return entity

    async def delete(self, entity_id: UUID) -> bool:
        entity = await self.get(entity_id)
        if not entity:
            return False

        await self.session.delete(entity)
        await self.session.commit()
        return True

    @staticmethod
    def _origin_source(entity: Entity, fallback: str) -> str:
        if entity.origin_source.strip():
            return entity.origin_source.strip()
        if entity.source.strip():
            return entity.source.strip()
        return fallback.strip() or "manual"
