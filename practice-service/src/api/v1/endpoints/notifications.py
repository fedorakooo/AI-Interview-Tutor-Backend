from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends
from jwt_handler.value_objects import AccessTokenPayload
from pydantic import BaseModel, Field

from src.api.security import require_authenticated

router = APIRouter(prefix="/notifications", tags=["Notifications"])

# Process-local inbox for MVP; replace with Mongo collection in multi-instance deploy.
_INBOX: dict[str, list[dict]] = {}


class NotificationItem(BaseModel):
    id: str
    title: str
    body: str
    created_at: datetime
    read: bool = False
    kind: str = "info"


class NotificationCreate(BaseModel):
    title: str
    body: str
    kind: str = "info"


@router.get("", response_model=list[NotificationItem])
async def list_notifications(
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
) -> list[NotificationItem]:
    items = _INBOX.get(payload["id"], [])
    return [NotificationItem.model_validate(item) for item in items]


@router.post("/mark-read/{notification_id}")
async def mark_read(
    notification_id: str,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
) -> dict[str, str]:
    for item in _INBOX.get(payload["id"], []):
        if item["id"] == notification_id:
            item["read"] = True
            return {"detail": "ok"}
    return {"detail": "not found"}


def push_notification(user_id: str, title: str, body: str, kind: str = "info") -> None:
    _INBOX.setdefault(user_id, []).insert(
        0,
        {
            "id": str(uuid4()),
            "title": title,
            "body": body,
            "created_at": datetime.now(UTC),
            "read": False,
            "kind": kind,
        },
    )
    # Cap inbox size
    _INBOX[user_id] = _INBOX[user_id][:50]
