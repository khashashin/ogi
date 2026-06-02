from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from ogi.config import settings
from ogi.models.auth import UserProfile
from ogi.models.billing import CloudSubscription, CloudTransformUsage


ACTIVE_SUBSCRIPTION_STATUSES = {"active", "trialing"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class BillingStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_subscription(self, user_id: UUID) -> CloudSubscription | None:
        return await self.session.get(CloudSubscription, user_id)

    async def get_subscription_by_customer_id(self, customer_id: str) -> CloudSubscription | None:
        if not customer_id:
            return None
        stmt = select(CloudSubscription).where(CloudSubscription.stripe_customer_id == customer_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def is_user_paid(self, user_id: UUID) -> bool:
        subscription = await self.get_subscription(user_id)
        if subscription is None:
            return False
        if subscription.status not in ACTIVE_SUBSCRIPTION_STATUSES:
            return False
        period_end = as_utc(subscription.current_period_end)
        return period_end is None or period_end > utc_now()

    async def is_admin(self, user_id: UUID) -> bool:
        admin_emails = set(settings.get_admin_emails())
        if not admin_emails:
            return False
        profile = await self.session.get(UserProfile, user_id)
        return bool(profile and profile.email.lower() in admin_emails)

    async def get_usage(self, user_id: UUID) -> CloudTransformUsage | None:
        return await self.session.get(CloudTransformUsage, user_id)

    async def touch_transform_usage(self, user_id: UUID) -> CloudTransformUsage:
        usage = await self.get_usage_for_update(user_id)
        now = utc_now()
        if usage is None:
            usage = CloudTransformUsage(user_id=user_id, last_transform_run_at=now, updated_at=now)
        else:
            usage.last_transform_run_at = now
            usage.updated_at = now
        self.session.add(usage)
        await self.session.commit()
        await self.session.refresh(usage)
        return usage

    async def get_usage_for_update(self, user_id: UUID) -> CloudTransformUsage | None:
        stmt = (
            select(CloudTransformUsage)
            .where(CloudTransformUsage.user_id == user_id)
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def upsert_subscription(
        self,
        *,
        user_id: UUID,
        stripe_customer_id: str = "",
        stripe_subscription_id: str = "",
        status: str = "none",
        price_id: str = "",
        amount_cents: int = 0,
        currency: str = "usd",
        cancel_at_period_end: bool = False,
        current_period_end: datetime | None = None,
    ) -> CloudSubscription:
        subscription = await self.get_subscription(user_id)
        if subscription is None:
            subscription = CloudSubscription(user_id=user_id)
        subscription.stripe_customer_id = stripe_customer_id or subscription.stripe_customer_id
        subscription.stripe_subscription_id = stripe_subscription_id or subscription.stripe_subscription_id
        subscription.status = status or subscription.status
        subscription.price_id = price_id or subscription.price_id
        subscription.amount_cents = amount_cents or subscription.amount_cents
        subscription.currency = (currency or subscription.currency or "usd").lower()
        subscription.cancel_at_period_end = cancel_at_period_end
        subscription.current_period_end = current_period_end
        subscription.updated_at = utc_now()
        self.session.add(subscription)
        await self.session.commit()
        await self.session.refresh(subscription)
        return subscription
