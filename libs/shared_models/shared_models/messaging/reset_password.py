from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ResetPasswordMessage(BaseModel):
    """RabbitMQ job published when a user requests a password reset."""

    model_config = ConfigDict(str_strip_whitespace=True)

    user_id: UUID
    email: str = Field(min_length=1, max_length=320)
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1)
    published_at: datetime

    @field_validator("published_at", mode="before")
    @classmethod
    def _parse_published_at(cls, value: datetime | str) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        return datetime.fromisoformat(value)
