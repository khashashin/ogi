"""add telemetry tables

Revision ID: a9b8c7d6e5f4
Revises: f7a8b9c0d1e2
Create Date: 2026-03-30 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "a9b8c7d6e5f4"
down_revision: str | Sequence[str] | None = "f7a8b9c0d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "telemetry_local_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("instance_id", sa.UUID(), nullable=False),
        sa.Column("instance_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_basic_sent_on", sa.Date(), nullable=True),
        sa.Column("last_full_sent_on", sa.Date(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_telemetry_local_state_instance_id"),
        "telemetry_local_state",
        ["instance_id"],
        unique=False,
    )

    op.create_table(
        "telemetry_installations",
        sa.Column("instance_id", sa.UUID(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("instance_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latest_ogi_version", sa.String(length=64), nullable=False),
        sa.Column("latest_telemetry_level", sa.String(length=16), nullable=False),
        sa.Column("deployment_mode", sa.String(length=32), nullable=False),
        sa.Column("latest_country_code", sa.String(length=8), nullable=True),
        sa.PrimaryKeyConstraint("instance_id"),
    )

    op.create_table(
        "telemetry_daily_metrics",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("instance_id", sa.UUID(), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("ogi_version", sa.String(length=64), nullable=False),
        sa.Column("telemetry_level", sa.String(length=16), nullable=False),
        sa.Column("deployment_mode", sa.String(length=32), nullable=False),
        sa.Column("country_code", sa.String(length=8), nullable=True),
        sa.Column("projects_total", sa.Integer(), nullable=True),
        sa.Column("entities_total", sa.Integer(), nullable=True),
        sa.Column("edges_total", sa.Integer(), nullable=True),
        sa.Column("transform_runs_total", sa.Integer(), nullable=True),
        sa.Column("investigator_runs_total", sa.Integer(), nullable=True),
        sa.Column("active_users_total", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["instance_id"], ["telemetry_installations.instance_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("instance_id", "metric_date"),
    )
    op.create_index(
        op.f("ix_telemetry_daily_metrics_instance_id"),
        "telemetry_daily_metrics",
        ["instance_id"],
        unique=False,
    )

    op.create_table(
        "telemetry_installed_transforms",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("daily_metric_id", sa.UUID(), nullable=False),
        sa.Column("transform_name", sa.String(length=255), nullable=False),
        sa.Column("transform_version", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["daily_metric_id"], ["telemetry_daily_metrics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("daily_metric_id", "transform_name"),
    )
    op.create_index(
        op.f("ix_telemetry_installed_transforms_daily_metric_id"),
        "telemetry_installed_transforms",
        ["daily_metric_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_telemetry_installed_transforms_daily_metric_id"), table_name="telemetry_installed_transforms")
    op.drop_table("telemetry_installed_transforms")
    op.drop_index(op.f("ix_telemetry_daily_metrics_instance_id"), table_name="telemetry_daily_metrics")
    op.drop_table("telemetry_daily_metrics")
    op.drop_table("telemetry_installations")
    op.drop_index(op.f("ix_telemetry_local_state_instance_id"), table_name="telemetry_local_state")
    op.drop_table("telemetry_local_state")
    op.drop_column("profiles", "last_active_at")
