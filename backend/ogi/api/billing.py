from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ogi.api.auth import get_current_user, get_optional_user
from ogi.billing import (
    BillingStatus,
    build_billing_status,
    cancel_supporter_subscription,
    is_billing_enabled,
    origin_url_from_request_headers,
    parse_stripe_event,
    stripe_post,
    sync_checkout_session,
    sync_subscription_from_stripe,
    verify_stripe_signature,
)
from ogi.config import settings
from ogi.db.database import get_session
from ogi.models import UserProfile
from ogi.store.billing_store import BillingStore

router = APIRouter(prefix="/billing", tags=["billing"])


class BillingSessionResponse(BaseModel):
    url: str


def _require_billing_enabled() -> None:
    if not is_billing_enabled():
        raise HTTPException(status_code=404, detail="Cloud billing is not enabled")


def _frontend_url(request: Request, explicit: str, fallback_path: str) -> str:
    if explicit:
        return explicit
    origin = origin_url_from_request_headers(dict(request.headers))
    if not origin:
        origin = str(request.base_url).rstrip("/")
    return f"{origin}{fallback_path}"


@router.get("/status", response_model=BillingStatus)
async def billing_status(
    current_user: UserProfile | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_session),
) -> BillingStatus:
    return await build_billing_status(session, current_user)


@router.post("/checkout-session", response_model=BillingSessionResponse)
async def create_checkout_session(
    request: Request,
    current_user: UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BillingSessionResponse:
    _require_billing_enabled()
    if not settings.stripe_checkout_enabled:
        raise HTTPException(status_code=503, detail="Stripe Checkout is not configured")

    store = BillingStore(session)
    existing = await store.get_subscription(current_user.id)
    data: dict[str, object] = {
        "mode": "subscription",
        "client_reference_id": str(current_user.id),
        "metadata[user_id]": str(current_user.id),
        "subscription_data[metadata][user_id]": str(current_user.id),
        "line_items[0][price]": settings.stripe_supporter_price_id,
        "line_items[0][quantity]": "1",
        "success_url": _frontend_url(
            request,
            settings.billing_success_url,
            "/projects?billing=success",
        ),
        "cancel_url": _frontend_url(
            request,
            settings.billing_cancel_url,
            "/projects?billing=cancelled",
        ),
        "allow_promotion_codes": "true",
    }
    if existing and existing.stripe_customer_id:
        data["customer"] = existing.stripe_customer_id
    elif current_user.email:
        data["customer_email"] = current_user.email

    stripe_session = await stripe_post("/checkout/sessions", data)
    url = str(stripe_session.get("url") or "")
    if not url:
        raise HTTPException(status_code=502, detail="Stripe Checkout did not return a URL")
    return BillingSessionResponse(url=url)


@router.post("/customer-portal", response_model=BillingSessionResponse)
async def create_customer_portal_session(
    request: Request,
    current_user: UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BillingSessionResponse:
    _require_billing_enabled()
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe is not configured")

    subscription = await BillingStore(session).get_subscription(current_user.id)
    if subscription is None or not subscription.stripe_customer_id:
        raise HTTPException(status_code=404, detail="No Stripe customer found")

    portal_session = await stripe_post(
        "/billing_portal/sessions",
        {
            "customer": subscription.stripe_customer_id,
            "return_url": _frontend_url(
                request,
                settings.billing_portal_return_url,
                "/projects",
            ),
        },
    )
    url = str(portal_session.get("url") or "")
    if not url:
        raise HTTPException(status_code=502, detail="Stripe portal did not return a URL")
    return BillingSessionResponse(url=url)


@router.post("/subscription/cancel", response_model=BillingStatus)
async def cancel_subscription(
    current_user: UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BillingStatus:
    _require_billing_enabled()
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe is not configured")
    return await cancel_supporter_subscription(session=session, user=current_user)


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    _require_billing_enabled()
    payload = await request.body()
    verify_stripe_signature(
        payload,
        request.headers.get("stripe-signature", ""),
        settings.stripe_webhook_secret,
    )
    event = parse_stripe_event(payload)
    event_type = str(event.get("type") or "")
    data = event.get("data")
    obj = data.get("object") if isinstance(data, dict) else None
    if not isinstance(obj, dict):
        return {"status": "ignored"}

    if event_type == "checkout.session.completed":
        await sync_checkout_session(session=session, checkout_session=obj)
    elif event_type in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        await sync_subscription_from_stripe(session=session, subscription=obj)

    return {"status": "accepted"}
