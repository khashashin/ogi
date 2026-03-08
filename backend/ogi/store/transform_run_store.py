from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

import aiosqlite

from ogi.models import TransformRun, TransformResult, TransformStatus


class TransformRunStore:
    """Transform run persistence – works with either aiosqlite.Connection or asyncpg.Pool."""

    def __init__(self, db: object) -> None:
        self.db = db
        self._is_sqlite = isinstance(db, aiosqlite.Connection)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def save(self, run: TransformRun) -> TransformRun:
        if self._is_sqlite:
            await self._sqlite_save(run)
        else:
            await self._pg_save(run)
        return run

    async def get(self, run_id: UUID) -> TransformRun | None:
        if self._is_sqlite:
            return await self._sqlite_get(run_id)
        return await self._pg_get(run_id)

    async def list_by_project(self, project_id: UUID) -> list[TransformRun]:
        if self._is_sqlite:
            return await self._sqlite_list(project_id)
        return await self._pg_list(project_id)

    # ------------------------------------------------------------------
    # SQLite implementation
    # ------------------------------------------------------------------

    async def _sqlite_save(self, run: TransformRun) -> None:
        db: aiosqlite.Connection = self.db  # type: ignore[assignment]
        result_json = run.result.model_dump_json() if run.result else None
        await db.execute(
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
        await db.commit()

    async def _sqlite_get(self, run_id: UUID) -> TransformRun | None:
        db: aiosqlite.Connection = self.db  # type: ignore[assignment]
        cursor = await db.execute("SELECT * FROM transform_runs WHERE id = ?", (str(run_id),))
        row = await cursor.fetchone()
        return self._sqlite_row(row) if row else None

    async def _sqlite_list(self, project_id: UUID) -> list[TransformRun]:
        db: aiosqlite.Connection = self.db  # type: ignore[assignment]
        cursor = await db.execute(
            "SELECT * FROM transform_runs WHERE project_id = ? ORDER BY created_at DESC",
            (str(project_id),),
        )
        rows = await cursor.fetchall()
        return [self._sqlite_row(row) for row in rows]

    @staticmethod
    def _sqlite_row(row: aiosqlite.Row) -> TransformRun:
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

    # ------------------------------------------------------------------
    # PostgreSQL implementation
    # ------------------------------------------------------------------

    async def _pg_save(self, run: TransformRun) -> None:
        pool = self.db
        result_json = run.result.model_dump_json() if run.result else None
        await pool.execute(  # type: ignore[union-attr]
            """INSERT INTO transform_runs
               (id, project_id, transform_name, input_entity_id, status, result, error, created_at, completed_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
               ON CONFLICT (id) DO UPDATE SET
                   status = EXCLUDED.status,
                   result = EXCLUDED.result,
                   error = EXCLUDED.error,
                   completed_at = EXCLUDED.completed_at""",
            run.id,
            run.project_id,
            run.transform_name,
            run.input_entity_id,
            run.status.value,
            result_json,
            run.error,
            run.started_at,
            run.completed_at,
        )

    async def _pg_get(self, run_id: UUID) -> TransformRun | None:
        pool = self.db
        row = await pool.fetchrow("SELECT * FROM transform_runs WHERE id = $1", run_id)  # type: ignore[union-attr]
        return self._pg_row(row) if row else None

    async def _pg_list(self, project_id: UUID) -> list[TransformRun]:
        pool = self.db
        rows = await pool.fetch(  # type: ignore[union-attr]
            "SELECT * FROM transform_runs WHERE project_id = $1 ORDER BY created_at DESC",
            project_id,
        )
        return [self._pg_row(row) for row in rows]

    @staticmethod
    def _pg_row(row: object) -> TransformRun:
        r = row
        result = None
        result_raw = r["result"]  # type: ignore[index]
        if result_raw:
            if isinstance(result_raw, str):
                result = TransformResult.model_validate_json(result_raw)
            else:
                result = TransformResult.model_validate(result_raw)
        return TransformRun(
            id=r["id"],  # type: ignore[index]
            project_id=r["project_id"],  # type: ignore[index]
            transform_name=r["transform_name"],  # type: ignore[index]
            input_entity_id=r["input_entity_id"],  # type: ignore[index]
            status=TransformStatus(r["status"]),  # type: ignore[index]
            result=result,
            error=r["error"],  # type: ignore[index]
            started_at=r["created_at"],  # type: ignore[index]
            completed_at=r["completed_at"],  # type: ignore[index]
        )
