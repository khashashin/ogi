from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker
from sqlmodel import SQLModel

from ogi.config import settings

# Import all models so SQLModel.metadata knows about them for create_all
import ogi.models.project  # noqa: F401
import ogi.models.entity  # noqa: F401
import ogi.models.edge  # noqa: F401
import ogi.models.auth  # noqa: F401
import ogi.models.transform  # noqa: F401
import ogi.models.api_key  # noqa: F401
import ogi.models.plugin  # noqa: F401

engine: AsyncEngine | None = None
async_session_maker: async_sessionmaker[AsyncSession] | None = None

async def init_db() -> None:
    global engine, async_session_maker

    if settings.use_sqlite:
        if settings.database_path == ":memory:":
            db_url = "sqlite+aiosqlite:///:memory:"
        else:
            db_url = f"sqlite+aiosqlite:///{settings.abs_database_path}"
        engine = create_async_engine(db_url, echo=False)
        # Create tables from SQLModel metadata (needed for in-memory / fresh SQLite DBs)
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
    else:
        db_url = settings.database_url
        if db_url and db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(
            db_url,
            echo=False,
            pool_size=5,
            max_overflow=10,
        )

    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )


async def close_db() -> None:
    global engine
    if engine is not None:
        await engine.dispose()
        engine = None


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    if async_session_maker is None:
        raise RuntimeError("Database not initialized")
    async with async_session_maker() as session:
        yield session
