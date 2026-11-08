"""The anonymous profile of no-auth mode is stored once, and only where it belongs.

PostgreSQL enforces the foreign keys to profiles.id, so a no-auth install could not create a
project while the anonymous user existed only in memory. These tests run on SQLite with foreign
keys switched on so they fail the same way PostgreSQL did.
"""
from collections.abc import AsyncIterator

import pytest
from fastapi import HTTPException
from sqlalchemy import event, func
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import ConnectionPoolEntry
from sqlmodel import SQLModel, select
from starlette.requests import Request

import ogi.models  # noqa: F401  -- register all tables on SQLModel.metadata
from ogi.api.auth import _ANON_USER, get_current_user
from ogi.config import settings
from ogi.models import Project, UserProfile


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite://")

    @event.listens_for(engine.sync_engine, "connect")
    def _enforce_foreign_keys(dbapi_connection: DBAPIConnection, _record: ConnectionPoolEntry) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest.fixture
def no_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "supabase_url", "")
    monkeypatch.setattr(settings, "supabase_anon_key", "")
    monkeypatch.setattr(settings, "deployment_mode", "self-hosted")


def _request(headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers or []})


async def _anonymous_profiles(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count()).select_from(UserProfile).where(UserProfile.id == _ANON_USER.id)
    )
    return int(result.scalar_one())


async def test_no_auth_stores_the_anonymous_profile_once(session: AsyncSession, no_auth: None) -> None:
    first = await get_current_user(_request(), session)
    second = await get_current_user(_request(), session)

    assert first.id == second.id == _ANON_USER.id
    assert await _anonymous_profiles(session) == 1


async def test_anonymous_user_can_own_a_project(session: AsyncSession, no_auth: None) -> None:
    session.add(Project(name="before", owner_id=_ANON_USER.id))
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()

    user = await get_current_user(_request(), session)
    session.add(Project(name="after", owner_id=user.id))
    await session.commit()


async def test_cloud_mode_without_auth_stores_nothing(
    session: AsyncSession, no_auth: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "deployment_mode", "cloud")

    user = await get_current_user(_request(), session)

    assert user.id == _ANON_USER.id
    assert await _anonymous_profiles(session) == 0


async def test_auth_enabled_never_falls_back_to_the_anonymous_user(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "supabase_url", "https://example.supabase.co")
    monkeypatch.setattr(settings, "supabase_anon_key", "anon-key")
    monkeypatch.setattr(settings, "deployment_mode", "self-hosted")

    with pytest.raises(HTTPException) as missing_token:
        await get_current_user(_request(), session)
    with pytest.raises(HTTPException) as empty_token:
        await get_current_user(_request([(b"authorization", b"Bearer ")]), session)

    assert missing_token.value.status_code == empty_token.value.status_code == 401
    assert await _anonymous_profiles(session) == 0
