"""Reset database and regenerate Alembic initial migration.

Usage:
    uv run python scripts/reset_db.py
    uv run python scripts/reset_db.py --no-migrate   # only reset, don't create migration
"""
import asyncio
import glob
import os
import sys

# Ensure the backend package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

from ogi.config import settings

VERSIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alembic", "versions")


async def reset_database() -> None:
    """Drop and recreate the public schema."""
    db_url = settings.database_url
    if db_url and db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if "?" in db_url:
            base, query = db_url.split("?", 1)
            params = [p for p in query.split("&") if not p.startswith("pgbouncer=")]
            if params:
                db_url = f"{base}?{'&'.join(params)}"
            else:
                db_url = base

    print(f"Connecting to: {db_url.split('@')[1] if '@' in db_url else db_url}")

    from sqlalchemy import pool
    import uuid
    engine = create_async_engine(
        db_url,
        poolclass=pool.NullPool,
        connect_args={
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__",
            "prepared_statement_cache_size": 0,
            "statement_cache_size": 0
        }
    )
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        # Grant permissions
        await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
        print("Database schema reset (all tables dropped)")
    await engine.dispose()


def delete_migrations() -> None:
    """Remove all migration files from alembic/versions/."""
    py_files = glob.glob(os.path.join(VERSIONS_DIR, "*.py"))
    count = 0
    for f in py_files:
        if os.path.basename(f) == "__init__.py":
            continue
        os.remove(f)
        count += 1
    # Also clear __pycache__
    cache_dir = os.path.join(VERSIONS_DIR, "__pycache__")
    if os.path.isdir(cache_dir):
        for f in glob.glob(os.path.join(cache_dir, "*")):
            os.remove(f)
    print(f"Deleted {count} migration file(s)")


def generate_migration() -> None:
    """Run alembic autogenerate to create a fresh initial migration."""
    import subprocess

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "revision", "--autogenerate", "-m", "initial_schema"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Autogenerate failed:\n{result.stderr}")
        sys.exit(1)
    print("Generated initial_schema migration")


def apply_migration() -> None:
    """Run alembic upgrade head."""
    import subprocess

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Migration failed:\n{result.stderr}")
        sys.exit(1)
    print("Migration applied -- database is ready!")


def main() -> None:
    no_migrate = "--no-migrate" in sys.argv

    print("=" * 50)
    print("  OGI Database Reset Script")
    print("=" * 50)

    # 1. Reset database
    asyncio.run(reset_database())

    # 2. Delete old migrations
    delete_migrations()

    if not no_migrate:
        # 3. Generate new migration
        generate_migration()

        # 4. Apply migration
        apply_migration()

    print("=" * 50)
    print("  Done!")
    print("=" * 50)


if __name__ == "__main__":
    main()
