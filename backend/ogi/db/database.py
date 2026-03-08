from __future__ import annotations

from typing import Union

import aiosqlite

from ogi.config import settings

# --- SQLite (legacy / local dev) ---

_sqlite_db: aiosqlite.Connection | None = None


async def get_sqlite_db() -> aiosqlite.Connection:
    global _sqlite_db
    if _sqlite_db is None:
        _sqlite_db = await aiosqlite.connect(settings.database_path)
        _sqlite_db.row_factory = aiosqlite.Row
        await _sqlite_db.execute("PRAGMA journal_mode=WAL")
        await _sqlite_db.execute("PRAGMA foreign_keys=ON")
    return _sqlite_db


async def close_sqlite_db() -> None:
    global _sqlite_db
    if _sqlite_db is not None:
        await _sqlite_db.close()
        _sqlite_db = None


# --- PostgreSQL (asyncpg) ---

try:
    import asyncpg  # noqa: F401
    _pg_pool: asyncpg.Pool | None = None
except ImportError:
    _pg_pool = None


async def create_pg_pool() -> "asyncpg.Pool":
    import asyncpg as _asyncpg

    global _pg_pool
    _pg_pool = await _asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=2,
        max_size=10,
    )
    return _pg_pool


def get_pg_pool() -> "asyncpg.Pool":
    assert _pg_pool is not None, "PostgreSQL pool not initialised"
    return _pg_pool


async def close_pg_pool() -> None:
    global _pg_pool
    if _pg_pool is not None:
        await _pg_pool.close()
        _pg_pool = None


# --- Unified helpers ---

DbConn = Union[aiosqlite.Connection, "asyncpg.Pool"]


async def get_db() -> DbConn:
    """Return the active DB connection/pool based on settings."""
    if settings.use_sqlite:
        return await get_sqlite_db()
    return get_pg_pool()


async def close_db() -> None:
    if settings.use_sqlite:
        await close_sqlite_db()
    else:
        await close_pg_pool()
