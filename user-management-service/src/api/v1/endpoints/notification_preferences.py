"""Notification preference center for the current user."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from jwt_handler.value_objects import AccessTokenPayload
from pydantic import BaseModel, Field

from src.api.security import require_authenticated
from src.api.dependencies.database import get_unit_of_work
from src.domain.interfaces.database.uow import IUnitOfWork
from src.infrastructure.postgres.schemas.notification_preference import NotificationPreferenceORM

router = APIRouter(prefix="/user/me/notification-preferences", tags=["Privacy"])

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
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
) -> NotificationPreferences:
    async with uow:
        stored = await uow.notification_preference_repository.get_by_user_id(UUID(payload["id"]))
    return NotificationPreferences.model_validate(stored, from_attributes=True) if stored else NotificationPreferences()


@router.put("", response_model=NotificationPreferences)
async def update_preferences(
    body: NotificationPreferences,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
) -> NotificationPreferences:
    async with uow:
        stored = await uow.notification_preference_repository.upsert(
            NotificationPreferenceORM(user_id=UUID(payload["id"]), **body.model_dump())
        )
    return NotificationPreferences.model_validate(stored, from_attributes=True)
