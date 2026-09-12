"""Notification preference center for the current user."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from jwt_handler.value_objects import AccessTokenPayload
from pydantic import BaseModel, Field

from src.api.security import require_authenticated

router = APIRouter(prefix="/user/me/notification-preferences", tags=["Privacy"])

_PREFS: dict[str, dict] = {}


class NotificationPreferences(BaseModel):
    email_product: bool = True
    email_marketing: bool = False
    email_interview_complete: bool = True
    email_plan_ready: bool = True
    email_weekly_digest: bool = True
    in_app: bool = True
    quiet_hours_start: int | None = Field(default=None, ge=0, le=23)
    quiet_hours_end: int | None = Field(default=None, ge=0, le=23)


@router.get("", response_model=NotificationPreferences)
async def get_preferences(
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
) -> NotificationPreferences:
    stored = _PREFS.get(payload["id"])
    return NotificationPreferences.model_validate(stored) if stored else NotificationPreferences()


@router.put("", response_model=NotificationPreferences)
async def update_preferences(
    body: NotificationPreferences,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
) -> NotificationPreferences:
    _PREFS[payload["id"]] = body.model_dump()
    return body
