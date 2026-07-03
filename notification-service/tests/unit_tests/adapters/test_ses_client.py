import logging
from unittest.mock import MagicMock

from botocore.exceptions import ClientError

from src.adapters.outbound.ses_client import SESClient


class TestSESClient:
    def test_returns_true_on_successful_send(self) -> None:
        boto_client = MagicMock()
        logger = MagicMock(spec=logging.Logger)
        client = SESClient(client=boto_client, sender_email="noreply@example.com", logger=logger)

        result = client.send_email("user@example.com", "Subject", "Body text")

        assert result is True
        boto_client.send_email.assert_called_once()

    def test_returns_false_on_client_error(self) -> None:
        boto_client = MagicMock()
        boto_client.send_email.side_effect = ClientError(
            {"Error": {"Code": "MessageRejected", "Message": "Email address is not verified"}},
            "SendEmail",
        )
        logger = MagicMock(spec=logging.Logger)
        client = SESClient(client=boto_client, sender_email="noreply@example.com", logger=logger)

        result = client.send_email("user@example.com", "Subject", "Body text")

        assert result is False
        logger.error.assert_called_once()
