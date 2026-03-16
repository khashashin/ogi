"""merge agent memory and settings heads

Revision ID: e6f7a8b9c0d1
Revises: c1d2e3f4a5b6, e5f6a7b8c9d0
Create Date: 2026-03-16 12:40:00
"""

from typing import Sequence, Union


revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = ("c1d2e3f4a5b6", "e5f6a7b8c9d0")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
