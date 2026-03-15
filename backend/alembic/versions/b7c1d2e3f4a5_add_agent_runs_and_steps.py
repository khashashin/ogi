"""add agent runs and steps

Revision ID: b7c1d2e3f4a5
Revises: f2b9c4d7a1e3
Create Date: 2026-03-15 03:45:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b7c1d2e3f4a5"
down_revision = "f2b9c4d7a1e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(length=36)
    json_type = postgresql.JSONB(astext_type=sa.Text()) if dialect == "postgresql" else sa.JSON()

    op.create_table(
        "agent_runs",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("project_id", uuid_type, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", uuid_type, sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("scope", json_type, nullable=False, server_default=sa.text("'{}'") if dialect != "postgresql" else sa.text("'{}'::jsonb")),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False, server_default=""),
        sa.Column("model", sa.Text(), nullable=False, server_default=""),
        sa.Column("config", json_type, nullable=False, server_default=sa.text("'{}'") if dialect != "postgresql" else sa.text("'{}'::jsonb")),
        sa.Column("budget", json_type, nullable=False, server_default=sa.text("'{}'") if dialect != "postgresql" else sa.text("'{}'::jsonb")),
        sa.Column("usage", json_type, nullable=False, server_default=sa.text("'{}'") if dialect != "postgresql" else sa.text("'{}'::jsonb")),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()") if dialect == "postgresql" else None),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()") if dialect == "postgresql" else None),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_runs_project_id", "agent_runs", ["project_id"], unique=False)
    op.create_index("ix_agent_runs_user_id", "agent_runs", ["user_id"], unique=False)
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"], unique=False)

    op.create_table(
        "agent_steps",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("run_id", uuid_type, sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("tool_name", sa.Text(), nullable=True),
        sa.Column("tool_input", json_type, nullable=True),
        sa.Column("tool_output", json_type, nullable=True),
        sa.Column("llm_output", sa.Text(), nullable=True),
        sa.Column("token_usage", json_type, nullable=True),
        sa.Column("approval_payload", json_type, nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("worker_id", sa.Text(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()") if dialect == "postgresql" else None),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_steps_run_id", "agent_steps", ["run_id"], unique=False)
    op.create_index("ix_agent_steps_step_number", "agent_steps", ["step_number"], unique=False)
    op.create_index("ix_agent_steps_type", "agent_steps", ["type"], unique=False)
    op.create_index("ix_agent_steps_status", "agent_steps", ["status"], unique=False)
    op.create_index("ix_agent_steps_status_created_at", "agent_steps", ["status", "created_at"], unique=False)
    op.create_index(
        "uq_agent_steps_run_id_step_number",
        "agent_steps",
        ["run_id", "step_number"],
        unique=True,
    )

    if dialect == "postgresql":
        op.execute(
            """
            CREATE UNIQUE INDEX uq_agent_runs_active_per_project
            ON agent_runs (project_id)
            WHERE status IN ('pending', 'running', 'paused')
            """
        )
    else:
        op.execute(
            """
            CREATE UNIQUE INDEX uq_agent_runs_active_per_project
            ON agent_runs (project_id)
            WHERE status IN ('pending', 'running', 'paused')
            """
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_agent_runs_active_per_project")
    op.drop_index("uq_agent_steps_run_id_step_number", table_name="agent_steps")
    op.drop_index("ix_agent_steps_status_created_at", table_name="agent_steps")
    op.drop_index("ix_agent_steps_status", table_name="agent_steps")
    op.drop_index("ix_agent_steps_type", table_name="agent_steps")
    op.drop_index("ix_agent_steps_step_number", table_name="agent_steps")
    op.drop_index("ix_agent_steps_run_id", table_name="agent_steps")
    op.drop_table("agent_steps")
    op.drop_index("ix_agent_runs_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_user_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_project_id", table_name="agent_runs")
    op.drop_table("agent_runs")
