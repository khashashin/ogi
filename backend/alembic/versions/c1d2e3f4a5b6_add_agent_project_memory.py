"""add agent project memory

Revision ID: c1d2e3f4a5b6
Revises: d4e5f6a7b8c9
Create Date: 2026-03-16 12:20:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c1d2e3f4a5b6"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    uuid_type = postgresql.UUID(as_uuid=True) if dialect == "postgresql" else sa.String(length=36)
    json_type = postgresql.JSONB(astext_type=sa.Text()) if dialect == "postgresql" else sa.JSON()
    json_default = sa.text("'[]'::jsonb") if dialect == "postgresql" else sa.text("'[]'")

    op.create_table(
        "agent_project_memory",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("project_id", uuid_type, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("known_facts", json_type, nullable=False, server_default=json_default),
        sa.Column("recent_findings", json_type, nullable=False, server_default=json_default),
        sa.Column("exhausted_paths", json_type, nullable=False, server_default=json_default),
        sa.Column("recent_runs", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()") if dialect == "postgresql" else None),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()") if dialect == "postgresql" else None),
    )
    op.create_index("ix_agent_project_memory_project_id", "agent_project_memory", ["project_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_agent_project_memory_project_id", table_name="agent_project_memory")
    op.drop_table("agent_project_memory")
