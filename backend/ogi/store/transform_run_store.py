import json
from datetime import datetime
from uuid import UUID

import aiosqlite

from ogi.models import TransformRun, TransformResult, TransformStatus


class TransformRunStore:
    def __init__(self, db: aiosqlite.Connection) -> None:
        self.db = db

    async def save(self, run: TransformRun) -> TransformRun:
        result_json = run.result.model_dump_json() if run.result else None
        await self.db.execute(
            """INSERT OR REPLACE INTO transform_runs
               (id, project_id, transform_name, input_entity_id, status, result, error, created_at, completed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(run.id),
                str(run.project_id),
                run.transform_name,
                str(run.input_entity_id),
                run.status.value,
                result_json,
                run.error,
                run.started_at.isoformat(),
                run.completed_at.isoformat() if run.completed_at else None,
            ),
        )
        await self.db.commit()
        return run

    async def get(self, run_id: UUID) -> TransformRun | None:
        cursor = await self.db.execute(
            "SELECT * FROM transform_runs WHERE id = ?", (str(run_id),)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_run(row)

    async def list_by_project(self, project_id: UUID) -> list[TransformRun]:
        cursor = await self.db.execute(
            "SELECT * FROM transform_runs WHERE project_id = ? ORDER BY created_at DESC",
            (str(project_id),),
        )
        rows = await cursor.fetchall()
        return [self._row_to_run(row) for row in rows]

    def _row_to_run(self, row: aiosqlite.Row) -> TransformRun:
        result = None
        if row["result"]:
            result = TransformResult.model_validate_json(row["result"])

        return TransformRun(
            id=UUID(row["id"]),
            project_id=UUID(row["project_id"]),
            transform_name=row["transform_name"],
            input_entity_id=UUID(row["input_entity_id"]),
            status=TransformStatus(row["status"]),
            result=result,
            error=row["error"],
            started_at=datetime.fromisoformat(row["created_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
        )
