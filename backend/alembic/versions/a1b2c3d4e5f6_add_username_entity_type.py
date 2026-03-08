"""add username entity type

Revision ID: a1b2c3d4e5f6
Revises: f2b9c4d7a1e3
Create Date: 2026-03-08 18:10:00
"""

from typing import Sequence, Union

from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f2b9c4d7a1e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'entitytype'
                  AND e.enumlabel = 'USERNAME'
            ) THEN
                ALTER TYPE entitytype ADD VALUE 'USERNAME';
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    # PostgreSQL enum values are not safely removable in-place.
    pass
