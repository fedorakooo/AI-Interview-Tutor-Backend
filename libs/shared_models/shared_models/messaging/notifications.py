from __future__ import annotations

from pydantic import BaseModel, Field


class VerifyEmailMessage(BaseModel):
    user_id: str
    email: str
    subject: str
    body: str
    email_type: str = "email_verify"
    published_at: str | None = None


class NotificationEmailMessage(BaseModel):
    """Generic outbound email notification payload."""

    user_id: str
    email: str
    subject: str
    body: str
    email_type: str = Field(description="email_verify | welcome | interview_complete | plan_ready | digest")
    published_at: str | None = None
