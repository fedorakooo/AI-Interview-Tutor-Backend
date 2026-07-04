import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aio_pika import DeliveryMode, IncomingMessage
from shared_models.messaging.retry_policy import (
    BASE_RETRY_DELAY_SECONDS,
    DLQ_ALERT_MARKER,
    MAX_RETRY_DELAY_SECONDS,
    MessageRetryPolicy,
    compute_backoff_delay,
    get_retry_count,
)


class TestGetRetryCount:
    def test_returns_zero_for_missing_headers(self) -> None:
        assert get_retry_count(None) == 0

    def test_returns_zero_for_missing_key(self) -> None:
        assert get_retry_count({}) == 0

    def test_parses_integer_header(self) -> None:
        assert get_retry_count({"x-retry-count": 2}) == 2

    def test_parses_string_header(self) -> None:
        assert get_retry_count({"x-retry-count": "1"}) == 1

    def test_returns_zero_for_invalid_header(self) -> None:
        assert get_retry_count({"x-retry-count": "invalid"}) == 0


class TestComputeBackoffDelay:
    def test_returns_zero_for_non_positive_retry_count(self) -> None:
        assert compute_backoff_delay(0) == 0.0

    def test_exponential_backoff(self) -> None:
        assert compute_backoff_delay(1) == BASE_RETRY_DELAY_SECONDS
        assert compute_backoff_delay(2) == BASE_RETRY_DELAY_SECONDS * 2
        assert compute_backoff_delay(3) == BASE_RETRY_DELAY_SECONDS * 4

    def test_caps_at_max_delay(self) -> None:
        assert compute_backoff_delay(10) == MAX_RETRY_DELAY_SECONDS


class TestMessageRetryPolicy:
    @pytest.mark.asyncio
    async def test_republish_with_retry_sets_header_and_applies_backoff(self) -> None:
        channel = AsyncMock()
        message = MagicMock(spec=IncomingMessage)
        message.body = b'{"email": "user@example.com"}'
        message.headers = {}
        message.delivery_mode = DeliveryMode.PERSISTENT
        message.routing_key = "reset-password-stream"

        policy = MessageRetryPolicy()
        with patch("shared_models.messaging.retry_policy.asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
            await policy.republish_with_retry(channel, message, retry_count=2)

        sleep_mock.assert_awaited_once_with(BASE_RETRY_DELAY_SECONDS * 2)
        channel.default_exchange.publish.assert_awaited_once()
        published_message = channel.default_exchange.publish.await_args.args[0]
        assert published_message.headers["x-retry-count"] == 2
        assert published_message.body == message.body

    @pytest.mark.asyncio
    async def test_send_to_dlq_publishes_headers_and_logs_alert(self) -> None:
        channel = AsyncMock()
        logger = MagicMock(spec=logging.Logger)

        policy = MessageRetryPolicy()
        await policy.send_to_dlq(
            channel,
            "reset-password-stream.dlq",
            b"{}",
            reason="invalid_json",
            original_queue="reset-password-stream",
            retry_count=0,
            logger=logger,
        )

        channel.default_exchange.publish.assert_awaited_once()
        published_message = channel.default_exchange.publish.await_args.args[0]
        assert published_message.headers["x-dead-letter-reason"] == "invalid_json"
        assert published_message.headers["x-original-queue"] == "reset-password-stream"
        assert published_message.headers["x-retry-count"] == 0

        logger.error.assert_called_once()
        assert logger.error.call_args.args[1] == DLQ_ALERT_MARKER
