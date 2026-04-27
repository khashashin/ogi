from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import Column, DateTime, Field, SQLModel, String


class CloudSubscription(SQLModel, table=True):
    __tablename__ = "cloud_subscriptions"

    user_id: UUID = Field(primary_key=True, foreign_key="profiles.id", ondelete="CASCADE")
    stripe_customer_id: str = Field(default="", sa_column=Column(String(length=255), nullable=False, index=True))
    stripe_subscription_id: str = Field(default="", sa_column=Column(String(length=255), nullable=False, index=True))
    status: str = Field(default="none", sa_column=Column(String(length=64), nullable=False))
    price_id: str = Field(default="", sa_column=Column(String(length=255), nullable=False))
    amount_cents: int = 0
    currency: str = Field(default="usd", sa_column=Column(String(length=16), nullable=False))
    cancel_at_period_end: bool = False
    current_period_end: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class CloudTransformUsage(SQLModel, table=True):
    __tablename__ = "cloud_transform_usage"

    user_id: UUID = Field(primary_key=True, foreign_key="profiles.id", ondelete="CASCADE")
    last_transform_run_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
