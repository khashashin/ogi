"""add agent step claim indexes

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-03-19 08:10:00
"""

from alembic import op


revision = "f7a8b9c0d1e2"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_agent_steps_claimable_created_step
        ON agent_steps (status, created_at, step_number)
        WHERE status IN ('pending', 'approved')
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_agent_steps_running_claimed_created_step
        ON agent_steps (claimed_at, created_at, step_number)
        WHERE status = 'running'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_agent_steps_running_claimed_created_step")
    op.execute("DROP INDEX IF EXISTS ix_agent_steps_claimable_created_step")
