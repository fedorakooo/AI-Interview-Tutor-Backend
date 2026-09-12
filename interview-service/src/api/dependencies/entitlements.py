from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

import httpx
from fastapi import Depends, HTTPException, status
from jwt_handler.value_objects import AccessTokenPayload
from shared_models.billing.entitlements import Entitlements, SubscriptionTier, TIER_LIMITS

from src.api.security import require_authenticated
from src.config import settings
from src.infrastructure.redis.client import create_redis_client

logger = logging.getLogger(__name__)


async def _fetch_entitlements(user_id: str) -> Entitlements:
    billing_base = settings.billing_service_url.rstrip("/")
    if billing_base:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{billing_base}/api/v1/billing/entitlements")
                if response.status_code == 200:
                    payload = response.json()
                    return Entitlements.model_validate(payload)
        except Exception:
            logger.warning("Billing entitlements lookup failed; using free tier defaults")

    return Entitlements.for_tier(SubscriptionTier.FREE)


async def _monthly_interview_usage(user_id: str) -> int:
    redis = create_redis_client()
    if redis is None:
        return 0
    month = datetime.now(UTC).strftime("%Y%m")
    key = f"entitlements:interviews:{user_id}:{month}"
    try:
        raw = await redis.get(key)
        return int(raw or 0)
    except Exception:
        logger.exception("Failed reading interview usage counter")
        return 0


async def _increment_interview_usage(user_id: str) -> None:
    redis = create_redis_client()
    if redis is None:
        return
    month = datetime.now(UTC).strftime("%Y%m")
    key = f"entitlements:interviews:{user_id}:{month}"
    try:
        await redis.incr(key)
        await redis.expire(key, 60 * 60 * 24 * 35)
    except Exception:
        logger.exception("Failed incrementing interview usage counter")


async def check_interview_quota_for_user(user_id: str) -> None:
    entitlements = await _fetch_entitlements(user_id)
    limit = entitlements.limits.get("interviews_per_month")
    if limit is None:
        limit = TIER_LIMITS[SubscriptionTier.FREE]["interviews_per_month"]
    used = await _monthly_interview_usage(user_id)
    if used >= limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error_code": "INTERVIEW_QUOTA_EXCEEDED",
                "message": "Monthly interview limit reached",
                "limit": limit,
                "used": used,
            },
        )


async def enforce_interview_quota(
    payload: AccessTokenPayload = Depends(require_authenticated),
) -> AccessTokenPayload:
    await check_interview_quota_for_user(str(payload["id"]))
    return payload


async def record_interview_started(user_id: UUID | str) -> None:
    await _increment_interview_usage(str(user_id))
