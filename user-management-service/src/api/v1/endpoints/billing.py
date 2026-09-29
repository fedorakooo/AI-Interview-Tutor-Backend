"""Billing & entitlements API (Stripe-ready; works in mock mode without Stripe keys)."""

from __future__ import annotations

import os
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from jwt_handler.value_objects import AccessTokenPayload
from shared_models.billing.entitlements import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    Entitlements,
    SubscriptionTier,
)

from src.api.security import require_authenticated, require_roles
from src.api.dependencies.database import get_unit_of_work
from src.domain.interfaces.database.uow import IUnitOfWork
from src.domain.value_objects.user_role import UserRole

router = APIRouter(prefix="/billing", tags=["Billing"])

def _stripe_enabled() -> bool:
    return bool(os.getenv("STRIPE_SECRET_KEY")) and os.getenv("FEATURE_STRIPE_BILLING", "false").lower() in {
        "1",
        "true",
        "yes",
    }


@router.get("/entitlements", response_model=Entitlements)
async def get_entitlements(
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
) -> Entitlements:
    async with uow:
        user = await uow.user_repository.get_by_id(UUID(payload["id"]))
    # An authenticated token whose account was deleted must not silently
    # receive free-plan access.
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account unavailable")
    return Entitlements.for_tier(user.subscription_tier)


@router.post("/checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    body: CheckoutSessionRequest,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
) -> CheckoutSessionResponse:
    user_id = payload["id"]

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

    # Local demo checkout intentionally has no external provider, but it is
    # still durable and therefore behaves correctly across a process restart.
    import uuid
    session_id = f"cs_mock_{uuid.uuid4().hex}"
    async with uow:
        user = await uow.user_repository.get_by_id(UUID(user_id))
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account unavailable")
        user.subscription_tier = body.tier.value
        await uow.user_repository.update(user)
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
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
) -> dict[str, str]:
    async with uow:
        user = await uow.user_repository.get_by_id(UUID(user_id))
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        user.subscription_tier = tier.value
        await uow.user_repository.update(user)
    return {"detail": f"Tier set to {tier.value}"}
