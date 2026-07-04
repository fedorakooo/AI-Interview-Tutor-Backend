from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from shared_models.messaging.reset_password import ResetPasswordMessage


class TestResetPasswordMessage:
    def test_accepts_iso_published_at(self) -> None:
        message = ResetPasswordMessage.model_validate(
            {
                "user_id": str(uuid4()),
                "email": "user@example.com",
                "subject": "Password Reset Request",
                "body": "Click the link to reset your password",
                "published_at": "2026-07-03T10:00:00+00:00",
            }
        )

        assert message.email == "user@example.com"
        assert message.published_at.tzinfo is not None

    def test_json_round_trip(self) -> None:
        original = ResetPasswordMessage(
            user_id=uuid4(),
            email="user@example.com",
            subject="Password Reset Request",
            body="Reset link",
            published_at=datetime.now(UTC),
        )
        restored = ResetPasswordMessage.model_validate_json(original.model_dump_json())
        assert restored == original

    def test_rejects_empty_email(self) -> None:
        with pytest.raises(ValidationError):
            ResetPasswordMessage.model_validate(
                {
                    "user_id": str(uuid4()),
                    "email": "",
                    "subject": "Password Reset Request",
                    "body": "Reset link",
                    "published_at": datetime.now(UTC).isoformat(),
                }
            )
