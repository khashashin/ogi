"""add_origin_source_to_entities

Revision ID: 8e4a7d2c1f21
Revises: c92513d84508
Create Date: 2026-03-07 15:05:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8e4a7d2c1f21"
down_revision: Union[str, Sequence[str], None] = "c92513d84508"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "entities",
        sa.Column("origin_source", sa.Text(), nullable=False, server_default="manual"),
    )
    op.execute("UPDATE entities SET origin_source = source WHERE origin_source IS NULL OR origin_source = ''")
    op.alter_column("entities", "origin_source", server_default=None)


def downgrade() -> None:
    op.drop_column("entities", "origin_source")
