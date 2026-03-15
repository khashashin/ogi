from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from ogi.config import settings

BASELINE_REVISION = "c92513d84508"
CORE_TABLES = ("projects", "entities", "edges", "transform_runs", "plugins")


def _normalized_async_db_url() -> str:
    db_url = settings.database_url
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if "?" in db_url:
            base, query = db_url.split("?", 1)
            params = [p for p in query.split("&") if not p.startswith("pgbouncer=")]
            db_url = f"{base}?{'&'.join(params)}" if params else base
    return db_url


def _alembic_config() -> Config:
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    return cfg


def _create_probe_engine():
    return create_async_engine(
        _normalized_async_db_url(),
        connect_args={
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__",
            "prepared_statement_cache_size": 0,
            "statement_cache_size": 0,
        },
    )


async def _table_exists(conn, table_name: str) -> bool:
    query = text(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = :table_name
        LIMIT 1
        """
    )
    result = await conn.execute(query, {"table_name": table_name})
    return result.scalar() == 1


async def _has_existing_app_schema() -> bool:
    engine = _create_probe_engine()
    try:
        async with engine.connect() as conn:
            for table_name in CORE_TABLES:
                if await _table_exists(conn, table_name):
                    return True
            return False
    finally:
        await engine.dispose()


async def _has_alembic_version_table() -> bool:
    engine = _create_probe_engine()
    try:
        async with engine.connect() as conn:
            return await _table_exists(conn, "alembic_version")
    finally:
        await engine.dispose()


async def adopt_and_upgrade() -> None:
    """Adopt pre-Alembic databases into the baseline revision, then upgrade."""
    if settings.use_sqlite:
        return

    cfg = _alembic_config()
    has_version = await _has_alembic_version_table()
    has_schema = await _has_existing_app_schema()

    if not has_version and has_schema:
        await asyncio.to_thread(command.stamp, cfg, BASELINE_REVISION)

    await asyncio.to_thread(command.upgrade, cfg, "head")


def main() -> None:
    asyncio.run(adopt_and_upgrade())


if __name__ == "__main__":
    main()
