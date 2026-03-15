"""merge agent and username heads

Revision ID: d4e5f6a7b8c9
Revises: a1b2c3d4e5f6, b7c1d2e3f4a5
Create Date: 2026-03-15 04:40:00
"""

from typing import Sequence, Union


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = ("a1b2c3d4e5f6", "b7c1d2e3f4a5")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
