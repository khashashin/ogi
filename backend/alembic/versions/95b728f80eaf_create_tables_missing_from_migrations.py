"""create the tables that had no migration

Five models were added without a migration: audit_logs, geocode_cache,
global_transform_settings, user_transform_settings, and
user_plugin_preferences. On PostgreSQL the schema comes only from Alembic, so
a fresh install never got them and every transform run failed with
"relation global_transform_settings does not exist". Databases that already
have them (created earlier by SQLModel's create_all) are left untouched: each
table is created only when it is missing, with the columns and indexes the
models define.

Revision ID: 95b728f80eaf
Revises: d8e1f2a3b4c5
Create Date: 2026-11-08 21:30:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "95b728f80eaf"
down_revision = "d8e1f2a3b4c5"
branch_labels = None
depends_on = None


def _create_audit_logs() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=False),
        sa.Column("resource_id", sa.String(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )


def _create_geocode_cache() -> None:
    op.create_table(
        "geocode_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query", sa.String(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_geocode_cache_query", "geocode_cache", ["query"], unique=True)


def _create_global_transform_settings() -> None:
    op.create_table(
        "global_transform_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transform_name", sa.String(), nullable=False),
        sa.Column("settings", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_global_transform_settings_transform_name",
        "global_transform_settings",
        ["transform_name"],
        unique=True,
    )


def _create_user_transform_settings() -> None:
    op.create_table(
        "user_transform_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transform_name", sa.String(), nullable=False),
        sa.Column("settings", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_user_transform_settings_user_id", "user_transform_settings", ["user_id"])
    op.create_index("ix_user_transform_settings_transform_name", "user_transform_settings", ["transform_name"])


def _create_user_plugin_preferences() -> None:
    op.create_table(
        "user_plugin_preferences",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plugin_name", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("user_id", "plugin_name"),
        sa.ForeignKeyConstraint(["user_id"], ["profiles.id"], ondelete="CASCADE"),
    )


_TABLES = {
    "audit_logs": _create_audit_logs,
    "geocode_cache": _create_geocode_cache,
    "global_transform_settings": _create_global_transform_settings,
    "user_transform_settings": _create_user_transform_settings,
    "user_plugin_preferences": _create_user_plugin_preferences,
}


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    for name, create in _TABLES.items():
        if name in existing:
            continue
        create()
        # The backend owns these tables and so is not subject to row-level security. Turning it on
        # (with no policies) keeps every other database role out, so a database that also serves
        # an HTTP API to other roles, such as Supabase's Data API with its public anon key, cannot
        # read or change transform settings or audit logs through it.
        op.execute(sa.text(f'ALTER TABLE "{name}" ENABLE ROW LEVEL SECURITY'))


def downgrade() -> None:
    # Deliberately a no-op. Most databases that reach this revision already had these tables
    # (production created them with create_all), and dropping them would delete transform
    # settings, plugin preferences and audit history that predate this migration.
    pass
