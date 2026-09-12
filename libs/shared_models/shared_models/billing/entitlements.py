from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class SubscriptionTier(StrEnum):
    FREE = "free"
    PRO = "pro"
    TEAM = "team"


TIER_LIMITS: dict[str, dict[str, int]] = {
    SubscriptionTier.FREE: {
        "interviews_per_month": 3,
        "practice_plans_per_day": 1,
        "voice_minutes_per_month": 0,
        "coding_runs_per_month": 10,
    },
    SubscriptionTier.PRO: {
        "interviews_per_month": 30,
        "practice_plans_per_day": 5,
        "voice_minutes_per_month": 120,
        "coding_runs_per_month": 200,
    },
    SubscriptionTier.TEAM: {
        "interviews_per_month": 200,
        "practice_plans_per_day": 20,
        "voice_minutes_per_month": 1000,
        "coding_runs_per_month": 2000,
    },
}


class CheckoutSessionRequest(BaseModel):
    tier: SubscriptionTier = SubscriptionTier.PRO
    success_url: str
    cancel_url: str


class CheckoutSessionResponse(BaseModel):
    checkout_url: str
    session_id: str


class Entitlements(BaseModel):
    tier: SubscriptionTier = SubscriptionTier.FREE
    limits: dict[str, int] = Field(default_factory=dict)
    usage: dict[str, int] = Field(default_factory=dict)

    @classmethod
    def for_tier(cls, tier: SubscriptionTier | str) -> "Entitlements":
        tier_value = SubscriptionTier(tier) if not isinstance(tier, SubscriptionTier) else tier
        return cls(tier=tier_value, limits=dict(TIER_LIMITS[tier_value]), usage={})
