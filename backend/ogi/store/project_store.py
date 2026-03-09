from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

import aiosqlite

from ogi.models import Project, ProjectCreate, ProjectUpdate


class ProjectStore:
    """Project CRUD – works with either aiosqlite.Connection or asyncpg.Pool."""

    def __init__(self, db: object) -> None:
        self.db = db
        self._is_sqlite = isinstance(db, aiosqlite.Connection)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create(self, data: ProjectCreate, owner_id: UUID) -> Project:
        project = Project(
            name=data.name, 
            description=data.description,
            owner_id=owner_id,
            is_public=data.is_public
        )
        if self._is_sqlite:
            await self._sqlite_insert(project)
        else:
            await self._pg_insert(project)
        return project

    async def get(self, project_id: UUID) -> Project | None:
        if self._is_sqlite:
            return await self._sqlite_get(project_id)
        return await self._pg_get(project_id)

    async def list_all(self, user_id: UUID) -> list[Project]:
        if self._is_sqlite:
            return await self._sqlite_list_all(user_id)
        return await self._pg_list_all(user_id)

    async def update(self, project_id: UUID, data: ProjectUpdate) -> Project | None:
        project = await self.get(project_id)
        if project is None:
            return None

        fields: dict[str, str] = {}
        if data.name is not None:
            fields["name"] = data.name
        if data.description is not None:
            fields["description"] = data.description
        if data.is_public is not None:
            fields["is_public"] = 1 if self._is_sqlite and data.is_public else data.is_public
        if not fields:
            return project

        now = datetime.now(timezone.utc)
        if self._is_sqlite:
            await self._sqlite_update(project_id, fields, now)
        else:
            await self._pg_update(project_id, fields, now)
        return await self.get(project_id)

    async def delete(self, project_id: UUID) -> bool:
        if self._is_sqlite:
            return await self._sqlite_delete(project_id)
        return await self._pg_delete(project_id)

    # ------------------------------------------------------------------
    # SQLite implementation
    # ------------------------------------------------------------------

    async def _sqlite_insert(self, project: Project) -> None:
        db: aiosqlite.Connection = self.db  # type: ignore[assignment]
        await db.execute(
            "INSERT INTO projects (id, name, description, owner_id, is_public, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(project.id),
                project.name,
                project.description,
                str(project.owner_id) if project.owner_id else None,
                1 if project.is_public else 0,
                project.created_at.isoformat(),
                project.updated_at.isoformat(),
            ),
        )
        await db.commit()

    async def _sqlite_get(self, project_id: UUID) -> Project | None:
        db: aiosqlite.Connection = self.db  # type: ignore[assignment]
        cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (str(project_id),))
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._sqlite_row_to_project(row)

    async def _sqlite_list_all(self, user_id: UUID) -> list[Project]:
        db: aiosqlite.Connection = self.db  # type: ignore[assignment]
        cursor = await db.execute(
            "SELECT * FROM projects WHERE owner_id = ? OR owner_id IS NULL OR is_public = 1 ORDER BY updated_at DESC",
            (str(user_id),)
        )
        rows = await cursor.fetchall()
        return [self._sqlite_row_to_project(row) for row in rows]

    async def _sqlite_update(self, project_id: UUID, fields: dict[str, str], now: datetime) -> None:
        db: aiosqlite.Connection = self.db  # type: ignore[assignment]
        updates = [f"{k} = ?" for k in fields]
        params: list[str] = list(fields.values())
        updates.append("updated_at = ?")
        params.append(now.isoformat())
        params.append(str(project_id))
        await db.execute(f"UPDATE projects SET {', '.join(updates)} WHERE id = ?", params)
        await db.commit()

    async def _sqlite_delete(self, project_id: UUID) -> bool:
        db: aiosqlite.Connection = self.db  # type: ignore[assignment]
        cursor = await db.execute("DELETE FROM projects WHERE id = ?", (str(project_id),))
        await db.commit()
        return cursor.rowcount > 0

    @staticmethod
    def _sqlite_row_to_project(row: aiosqlite.Row) -> Project:
        return Project(
            id=UUID(row["id"]),
            name=row["name"],
            description=row["description"],
            owner_id=UUID(row["owner_id"]) if "owner_id" in row.keys() and row["owner_id"] else None,
            is_public=bool(row["is_public"]) if "is_public" in row.keys() else False,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # ------------------------------------------------------------------
    # PostgreSQL implementation
    # ------------------------------------------------------------------

    async def _pg_insert(self, project: Project) -> None:
        pool = self.db  # asyncpg.Pool
        await pool.execute(  # type: ignore[union-attr]
            "INSERT INTO projects (id, name, description, owner_id, is_public, created_at, updated_at) VALUES ($1, $2, $3, $4, $5, $6, $7)",
            project.id,
            project.name,
            project.description,
            project.owner_id,
            project.is_public,
            project.created_at,
            project.updated_at,
        )

    async def _pg_get(self, project_id: UUID) -> Project | None:
        pool = self.db
        row = await pool.fetchrow("SELECT * FROM projects WHERE id = $1", project_id)  # type: ignore[union-attr]
        if row is None:
            return None
        return self._pg_row_to_project(row)

    async def _pg_list_all(self, user_id: UUID) -> list[Project]:
        pool = self.db
        rows = await pool.fetch(
            "SELECT * FROM projects WHERE owner_id = $1 OR owner_id IS NULL OR is_public = true ORDER BY updated_at DESC", 
            user_id
        )  # type: ignore[union-attr]
        return [self._pg_row_to_project(row) for row in rows]

    async def _pg_update(self, project_id: UUID, fields: dict[str, str], now: datetime) -> None:
        pool = self.db
        set_clauses: list[str] = []
        params: list[object] = []
        idx = 1
        for k, v in fields.items():
            set_clauses.append(f"{k} = ${idx}")
            params.append(v)
            idx += 1
        set_clauses.append(f"updated_at = ${idx}")
        params.append(now)
        idx += 1
        params.append(project_id)
        await pool.execute(  # type: ignore[union-attr]
            f"UPDATE projects SET {', '.join(set_clauses)} WHERE id = ${idx}",
            *params,
        )

    async def _pg_delete(self, project_id: UUID) -> bool:
        pool = self.db
        result = await pool.execute("DELETE FROM projects WHERE id = $1", project_id)  # type: ignore[union-attr]
        return result == "DELETE 1"

    @staticmethod
    def _pg_row_to_project(row: object) -> Project:
        return Project(
            id=row["id"],  # type: ignore[index]
            name=row["name"],  # type: ignore[index]
            description=row["description"],  # type: ignore[index]
            owner_id=row.get("owner_id"),  # type: ignore[union-attr]
            is_public=row.get("is_public", False),  # type: ignore[union-attr]
            created_at=row["created_at"],  # type: ignore[index]
            updated_at=row["updated_at"],  # type: ignore[index]
        )
