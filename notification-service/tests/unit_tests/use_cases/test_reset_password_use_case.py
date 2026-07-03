from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.application.use_cases.reset_password_use_case import ResetPasswordUseCase
from src.domain.exceptions.not_sent_error import NotSentError


class TestResetPasswordUseCase:
    def test_sends_email_on_first_attempt(self, sample_reset_password_payload: dict) -> None:
        mongo_repository = MagicMock()
        ses_client = MagicMock()
        ses_client.send_email.return_value = True

        ResetPasswordUseCase(mongo_repository, ses_client)(sample_reset_password_payload)

        mongo_repository.insert_one.assert_called_once()
        ses_client.send_email.assert_called_once_with(
            sample_reset_password_payload["email"],
            sample_reset_password_payload["subject"],
            sample_reset_password_payload["body"],
        )

    def test_retries_ses_until_success(self, sample_reset_password_payload: dict) -> None:
        mongo_repository = MagicMock()
        ses_client = MagicMock()
        ses_client.send_email.side_effect = [False, False, True]

        ResetPasswordUseCase(mongo_repository, ses_client)(sample_reset_password_payload)

        assert ses_client.send_email.call_count == 3

    def test_raises_not_sent_error_after_five_failures(self, sample_reset_password_payload: dict) -> None:
        mongo_repository = MagicMock()
        ses_client = MagicMock()
        ses_client.send_email.return_value = False

        with pytest.raises(NotSentError) as exc_info:
            ResetPasswordUseCase(mongo_repository, ses_client)(sample_reset_password_payload)

        assert exc_info.value.recipient == sample_reset_password_payload["email"]
        assert exc_info.value.attempts == 5
        assert ses_client.send_email.call_count == 5

    def test_persists_message_before_ses_retries(self, sample_reset_password_payload: dict) -> None:
        mongo_repository = MagicMock()
        ses_client = MagicMock()
        ses_client.send_email.return_value = True
        call_order: list[str] = []

        mongo_repository.insert_one.side_effect = lambda _: call_order.append("insert")
        ses_client.send_email.side_effect = lambda *args, **kwargs: call_order.append("send") or True

        ResetPasswordUseCase(mongo_repository, ses_client)(sample_reset_password_payload)

        assert call_order == ["insert", "send"]

    def test_raises_validation_error_on_invalid_payload(self) -> None:
        mongo_repository = MagicMock()
        ses_client = MagicMock()

        with pytest.raises(ValidationError):
            ResetPasswordUseCase(mongo_repository, ses_client)({"user_id": str(uuid4())})

        mongo_repository.insert_one.assert_not_called()
        ses_client.send_email.assert_not_called()

    def test_uses_mongo_transaction_context(self, sample_reset_password_payload: dict) -> None:
        mongo_repository = MagicMock()
        mongo_repository.__enter__ = MagicMock(return_value=mongo_repository)
        mongo_repository.__exit__ = MagicMock(return_value=False)
        ses_client = MagicMock()
        ses_client.send_email.return_value = True

        ResetPasswordUseCase(mongo_repository, ses_client)(sample_reset_password_payload)

        mongo_repository.__enter__.assert_called_once()
        mongo_repository.__exit__.assert_called_once()
