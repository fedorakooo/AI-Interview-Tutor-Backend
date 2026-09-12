"""Billing & entitlements API (Stripe-ready; works in mock mode without Stripe keys)."""

from __future__ import annotations

import os
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from jwt_handler.value_objects import AccessTokenPayload
from shared_models.billing.entitlements import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    Entitlements,
    SubscriptionTier,
)

from src.api.security import require_authenticated, require_roles
from src.domain.value_objects.user_role import UserRole

router = APIRouter(prefix="/billing", tags=["Billing"])

# In-memory usage counters for local/dev; replace with Redis/Postgres in production.
_USAGE: dict[str, dict[str, int]] = {}
_USER_TIERS: dict[str, str] = {}


def _stripe_enabled() -> bool:
    return bool(os.getenv("STRIPE_SECRET_KEY")) and os.getenv("FEATURE_STRIPE_BILLING", "false").lower() in {
        "1",
        "true",
        "yes",
    }


@router.get("/entitlements", response_model=Entitlements)
async def get_entitlements(
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
) -> Entitlements:
    user_id = payload["id"]
    tier = SubscriptionTier(_USER_TIERS.get(user_id, "free"))
    entitlements = Entitlements.for_tier(tier)
    entitlements.usage = dict(_USAGE.get(user_id, {}))
    return entitlements


@router.post("/checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    body: CheckoutSessionRequest,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
) -> CheckoutSessionResponse:
    user_id = payload["id"]
    session_id = f"cs_mock_{uuid.uuid4().hex}"

    if _stripe_enabled():
        try:
            import stripe

            stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
            price_map = {
                SubscriptionTier.PRO: os.getenv("STRIPE_PRICE_PRO"),
                SubscriptionTier.TEAM: os.getenv("STRIPE_PRICE_TEAM"),
            }
            price_id = price_map.get(body.tier)
            if not price_id:
                raise HTTPException(status_code=400, detail="Price not configured for tier")
            session = stripe.checkout.Session.create(
                mode="subscription",
                success_url=body.success_url,
                cancel_url=body.cancel_url,
                line_items=[{"price": price_id, "quantity": 1}],
                client_reference_id=user_id,
                metadata={"tier": body.tier.value},
            )
            return CheckoutSessionResponse(checkout_url=session.url, session_id=session.id)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Stripe error: {exc}") from exc

    # Mock checkout: immediately upgrade entitlements for local demos.
    _USER_TIERS[user_id] = body.tier.value
    return CheckoutSessionResponse(
        checkout_url=f"{body.success_url}?session_id={session_id}&tier={body.tier.value}",
        session_id=session_id,
    )


@router.post("/webhook")
async def stripe_webhook() -> dict[str, str]:
    """Placeholder Stripe webhook endpoint — wire signature verification in production."""
    return {"detail": "ok"}


@router.post("/admin/set-tier/{user_id}")
async def admin_set_tier(
    user_id: str,
    tier: SubscriptionTier,
    _: Annotated[AccessTokenPayload, Depends(require_roles(UserRole.ADMIN))],
) -> dict[str, str]:
    _USER_TIERS[user_id] = tier.value
    return {"detail": f"Tier set to {tier.value}"}
