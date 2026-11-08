"""Every table the models define must be created by an Alembic migration.

On PostgreSQL the schema comes only from the migrations (SQLite uses create_all), so a model
added without one works in the tests and in local SQLite mode but is missing on every fresh
PostgreSQL install. Five tables shipped that way and broke every transform run there.
"""
import ast
from pathlib import Path

from sqlmodel import SQLModel

import ogi.models  # noqa: F401  -- register all tables on SQLModel.metadata

VERSIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _tables_created_by_migrations() -> set[str]:
    """Names passed as the first argument to op.create_table(...) in any migration."""
    names: set[str] = set()
    for path in VERSIONS_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "create_table"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                names.add(node.args[0].value)
    return names


def test_every_model_table_has_a_migration() -> None:
    missing = sorted(set(SQLModel.metadata.tables) - _tables_created_by_migrations())
    assert not missing, (
        f"No Alembic migration creates {missing}. Add one in backend/alembic/versions, "
        "otherwise fresh PostgreSQL installs won't have these tables."
    )
