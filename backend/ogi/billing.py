from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from uuid import UUID

import httpx
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ogi.config import settings
from ogi.models import UserProfile
from ogi.store.billing_store import BillingStore, ACTIVE_SUBSCRIPTION_STATUSES, as_utc, utc_now


STRIPE_API_BASE = "https://api.stripe.com/v1"


class BillingStatus(BaseModel):
    billing_enabled: bool
    checkout_enabled: bool
    subscribed: bool
    subscription_status: str
    plan_name: str
    amount_cents: int
    currency: str
    free_transform_cooldown_seconds: int
    paid_transform_cooldown_seconds: int
    cancel_at_period_end: bool = False
    current_period_end: datetime | None = None
    last_transform_run_at: datetime | None = None
    next_allowed_transform_at: datetime | None = None
    retry_after_seconds: int = 0


def origin_url_from_request_headers(headers: dict[str, str]) -> str:
    origin = headers.get("origin") or headers.get("referer") or ""
    if origin:
        parts = origin.split("/", 3)
        if len(parts) >= 3:
            return f"{parts[0]}//{parts[2]}"
    return ""


def is_billing_enabled() -> bool:
    return settings.effective_cloud_billing_enabled


def _safe_cooldown(value: int) -> int:
    return max(0, int(value))


async def build_billing_status(session: AsyncSession, user: UserProfile | None) -> BillingStatus:
    billing_enabled = is_billing_enabled()
    store = BillingStore(session)
    subscribed = False
    status = "disabled" if not billing_enabled else "free"
    cancel_at_period_end = False
    current_period_end = None
    last_run = None
    next_allowed = None
    retry_after = 0

    if billing_enabled and user is not None:
        subscribed = await store.is_user_paid(user.id)
        subscription = await store.get_subscription(user.id)
        if subscription is not None:
            status = subscription.status
            cancel_at_period_end = subscription.cancel_at_period_end
            current_period_end = as_utc(subscription.current_period_end)
        usage = await store.get_usage(user.id)
        last_run = as_utc(usage.last_transform_run_at) if usage else None
        if not subscribed and last_run is not None:
            next_allowed = last_run + timedelta(seconds=_safe_cooldown(settings.free_transform_cooldown_seconds))
            remaining = (next_allowed - utc_now()).total_seconds()
            retry_after = max(0, int(remaining))
            if retry_after == 0:
                next_allowed = None

    return BillingStatus(
        billing_enabled=billing_enabled,
        checkout_enabled=settings.stripe_checkout_enabled,
        subscribed=subscribed,
        subscription_status=status,
        plan_name="Supporter",
        amount_cents=settings.stripe_supporter_amount_cents,
        currency=settings.stripe_supporter_currency.lower(),
        free_transform_cooldown_seconds=_safe_cooldown(settings.free_transform_cooldown_seconds),
        paid_transform_cooldown_seconds=_safe_cooldown(settings.paid_transform_cooldown_seconds),
        cancel_at_period_end=cancel_at_period_end,
        current_period_end=current_period_end,
        last_transform_run_at=last_run,
        next_allowed_transform_at=next_allowed,
        retry_after_seconds=retry_after,
    )


async def enforce_transform_run_policy(
    *,
    session: AsyncSession,
    user_id: UUID,
) -> None:
    if not is_billing_enabled():
        return

    store = BillingStore(session)
    if await store.is_admin(user_id):
        return

    subscribed = await store.is_user_paid(user_id)
    cooldown = (
        settings.paid_transform_cooldown_seconds
        if subscribed
        else settings.free_transform_cooldown_seconds
    )
    cooldown = _safe_cooldown(cooldown)
    if cooldown <= 0:
        if not subscribed:
            await store.touch_transform_usage(user_id)
        return

    usage = await store.get_usage_for_update(user_id)
    now = utc_now()
    last_run = as_utc(usage.last_transform_run_at) if usage else None
    if last_run is not None:
        next_allowed = last_run + timedelta(seconds=cooldown)
        if next_allowed > now:
            retry_after = max(1, int((next_allowed - now).total_seconds()))
            minutes = max(1, int((retry_after + 59) // 60))
            account_label = "Supporter accounts" if subscribed else "Free cloud accounts"
            upgrade_hint = "" if subscribed else ", or upgrade to Supporter"
            raise HTTPException(
                status_code=429,
                detail=(
                    f"{account_label} can run one transform every "
                    f"{max(1, cooldown // 60)} minutes. Try again in about "
                    f"{minutes} minute{'s' if minutes != 1 else ''}{upgrade_hint}."
                ),
                headers={"Retry-After": str(retry_after)},
            )

    if usage is None:
        usage = await store.touch_transform_usage(user_id)
    else:
        usage.last_transform_run_at = now
        usage.updated_at = now
        session.add(usage)
        await session.commit()


def verify_stripe_signature(payload: bytes, signature_header: str, webhook_secret: str) -> None:
    if not webhook_secret:
        raise HTTPException(status_code=503, detail="Stripe webhook secret is not configured")
    parts: dict[str, list[str]] = {}
    for item in signature_header.split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        parts.setdefault(key, []).append(value)
    timestamp = parts.get("t", [""])[0]
    signatures = parts.get("v1", [])
    if not timestamp or not signatures:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature header")
    signed_payload = f"{timestamp}.{payload.decode()}".encode()
    expected = hmac.new(webhook_secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, signature) for signature in signatures):
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")
    try:
        timestamp_value = int(timestamp)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature timestamp") from exc
    if abs(time.time() - timestamp_value) > 300:
        raise HTTPException(status_code=400, detail="Expired Stripe signature")


async def stripe_post(path: str, data: dict[str, object]) -> dict[str, object]:
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe is not configured")
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{STRIPE_API_BASE}{path}",
            data=data,
            auth=(settings.stripe_secret_key, ""),
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Stripe request failed")
    return response.json()


async def stripe_get(path: str) -> dict[str, object]:
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe is not configured")
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{STRIPE_API_BASE}{path}",
            auth=(settings.stripe_secret_key, ""),
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Stripe request failed")
    return response.json()


async def cancel_supporter_subscription(
    *,
    session: AsyncSession,
    user: UserProfile,
) -> BillingStatus:
    store = BillingStore(session)
    subscription = await store.get_subscription(user.id)
    if subscription is None or not subscription.stripe_subscription_id:
        raise HTTPException(status_code=404, detail="No active Supporter subscription found")
    if subscription.status not in ACTIVE_SUBSCRIPTION_STATUSES:
        raise HTTPException(status_code=409, detail="Supporter subscription is not active")
    if subscription.cancel_at_period_end:
        return await build_billing_status(session, user)

    stripe_subscription = await stripe_post(
        f"/subscriptions/{quote(subscription.stripe_subscription_id, safe='')}",
        {"cancel_at_period_end": "true"},
    )
    await sync_subscription_from_stripe(
        session=session,
        subscription=stripe_subscription,
        fallback_user_id=user.id,
    )
    return await build_billing_status(session, user)


def _period_end_from_subscription(subscription: dict[str, object]) -> datetime | None:
    raw = subscription.get("current_period_end")
    if raw is None:
        return None
    try:
        return datetime.fromtimestamp(int(raw), tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def _price_from_subscription(subscription: dict[str, object]) -> tuple[str, int, str]:
    items = subscription.get("items")
    data = items.get("data", []) if isinstance(items, dict) else []
    first = data[0] if isinstance(data, list) and data else {}
    price = first.get("price", {}) if isinstance(first, dict) else {}
    if not isinstance(price, dict):
        return "", 0, "usd"
    return (
        str(price.get("id") or ""),
        int(price.get("unit_amount") or 0),
        str(price.get("currency") or "usd").lower(),
    )


async def sync_subscription_from_stripe(
    *,
    session: AsyncSession,
    subscription: dict[str, object],
    fallback_user_id: UUID | None = None,
) -> None:
    metadata = subscription.get("metadata")
    user_id_raw = metadata.get("user_id") if isinstance(metadata, dict) else None
    customer_id = str(subscription.get("customer") or "")
    store = BillingStore(session)
    user_id: UUID | None = None
    if user_id_raw:
        try:
            user_id = UUID(str(user_id_raw))
        except ValueError:
            user_id = None
    if user_id is None and fallback_user_id is not None:
        user_id = fallback_user_id
    if user_id is None:
        existing = await store.get_subscription_by_customer_id(customer_id)
        user_id = existing.user_id if existing is not None else None
    if user_id is None:
        return

    price_id, amount_cents, currency = _price_from_subscription(subscription)
    await store.upsert_subscription(
        user_id=user_id,
        stripe_customer_id=customer_id,
        stripe_subscription_id=str(subscription.get("id") or ""),
        status=str(subscription.get("status") or "none"),
        price_id=price_id,
        amount_cents=amount_cents,
        currency=currency,
        cancel_at_period_end=bool(subscription.get("cancel_at_period_end")),
        current_period_end=_period_end_from_subscription(subscription),
    )


async def sync_checkout_session(
    *,
    session: AsyncSession,
    checkout_session: dict[str, object],
) -> None:
    metadata = checkout_session.get("metadata")
    user_id_raw = metadata.get("user_id") if isinstance(metadata, dict) else None
    if not user_id_raw:
        return
    try:
        user_id = UUID(str(user_id_raw))
    except ValueError:
        return
    customer_id = str(checkout_session.get("customer") or "")
    subscription_id = str(checkout_session.get("subscription") or "")
    store = BillingStore(session)
    await store.upsert_subscription(
        user_id=user_id,
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
        status="checkout_completed",
        price_id=settings.stripe_supporter_price_id,
        amount_cents=settings.stripe_supporter_amount_cents,
        currency=settings.stripe_supporter_currency,
        current_period_end=None,
    )
    if subscription_id:
        subscription = await stripe_get(f"/subscriptions/{subscription_id}")
        await sync_subscription_from_stripe(
            session=session,
            subscription=subscription,
            fallback_user_id=user_id,
        )


def parse_stripe_event(payload: bytes) -> dict[str, object]:
    try:
        event = json.loads(payload.decode())
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook payload") from exc
    if not isinstance(event, dict):
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook event")
    return event


def subscription_is_active(status: str) -> bool:
    return status in ACTIVE_SUBSCRIPTION_STATUSES
