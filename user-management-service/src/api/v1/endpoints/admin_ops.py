"""Admin ops endpoints for DLQ visibility, feature flags, and LLM spend placeholders."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from jwt_handler.value_objects import AccessTokenPayload
from shared_models.feature_flags.flags import FEATURE_DEFAULTS, feature_enabled

from src.api.security import require_roles
from src.domain.value_objects.user_role import UserRole

router = APIRouter(prefix="/admin/ops", tags=["Admin Ops"])


@router.get("/feature-flags")
async def list_feature_flags(
    _: Annotated[AccessTokenPayload, Depends(require_roles(UserRole.ADMIN))],
) -> dict[str, bool]:
    return {name: feature_enabled(name, default) for name, default in FEATURE_DEFAULTS.items()}


@router.get("/health-summary")
async def health_summary(
    _: Annotated[AccessTokenPayload, Depends(require_roles(UserRole.ADMIN, UserRole.MODERATOR))],
) -> dict:
    return {
        "queues": {
            "cv-analyze-stream": {"lag": None, "note": "Wire RabbitMQ management API"},
            "practice-plan-stream": {"lag": None},
            "practice-plan-ready-stream": {"lag": None},
        },
        "llm_spend": {
            "period": "current_month",
            "estimated_usd": None,
            "note": "Connect Langfuse / provider billing exports",
        },
        "dlq": {
            "cv-analyze-stream.dlq": {"depth": None},
            "practice-plan-stream.dlq": {"depth": None},
        },
    }
