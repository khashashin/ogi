import json
from datetime import datetime, timezone
from uuid import UUID

import aiosqlite

from ogi.models import Project, ProjectCreate


class ProjectStore:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def create(self, data: ProjectCreate) -> Project:
        project = Project(name=data.name, description=data.description)
        await self.db.execute(
            "INSERT INTO projects (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (
                str(project.id),
                project.name,
                project.description,
                project.created_at.isoformat(),
                project.updated_at.isoformat(),
            ),
        )
        await self.db.commit()
        return project

    async def get(self, project_id: UUID) -> Project | None:
        cursor = await self.db.execute(
            "SELECT * FROM projects WHERE id = ?", (str(project_id),)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_project(row)

    async def list_all(self) -> list[Project]:
        cursor = await self.db.execute(
            "SELECT * FROM projects ORDER BY updated_at DESC"
        )
        rows = await cursor.fetchall()
        return [self._row_to_project(row) for row in rows]

    async def delete(self, project_id: UUID) -> bool:
        cursor = await self.db.execute(
            "DELETE FROM projects WHERE id = ?", (str(project_id),)
        )
        await self.db.commit()
        return cursor.rowcount > 0

    def _row_to_project(self, row: aiosqlite.Row) -> Project:
        return Project(
            id=UUID(row["id"]),
            name=row["name"],
            description=row["description"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
