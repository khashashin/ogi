"""Access-control regression tests for ProjectStore.

A project with ``owner_id = NULL`` (an orphaned project) must never grant
owner rights or leak into other users' listings. See the
reassign-projects-on-owner-delete migration for how NULL owners are now
avoided in the first place; these tests guard the fail-closed behaviour in
case one slips through anyway.
"""
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

import ogi.models  # noqa: F401  -- register all tables on SQLModel.metadata
from ogi.models import Project
from ogi.store.project_store import ProjectStore


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest.mark.asyncio
async def test_null_owner_does_not_grant_owner_role(session):
    store = ProjectStore(session)
    project = Project(name="orphaned", owner_id=None, is_public=False)
    session.add(project)
    await session.commit()
    await session.refresh(project)

    # Any other user must get no access, NOT "owner".
    assert await store.get_member_role(project.id, uuid4()) is None


@pytest.mark.asyncio
async def test_null_owner_private_project_hidden_from_list_all(session):
    store = ProjectStore(session)
    session.add(Project(name="orphaned", owner_id=None, is_public=False))
    await session.commit()

    assert await store.list_all(uuid4()) == []


@pytest.mark.asyncio
async def test_real_owner_still_gets_owner_role(session):
    store = ProjectStore(session)
    uid = uuid4()
    project = Project(name="mine", owner_id=uid, is_public=False)
    session.add(project)
    await session.commit()
    await session.refresh(project)

    assert await store.get_member_role(project.id, uid) == "owner"
    assert [p.id for p in await store.list_all(uid)] == [project.id]
