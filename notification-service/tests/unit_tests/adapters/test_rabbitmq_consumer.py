import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aio_pika import IncomingMessage
from shared_models.messaging.retry_policy import MessageRetryPolicy

from src.adapters.inbound.rabbitmq_consumer import RabbitMQConsumer
from src.application.use_cases.reset_password_use_case import ResetPasswordUseCase
from src.domain.exceptions.not_sent_error import NotSentError


@pytest.fixture
def logger() -> logging.Logger:
    return logging.getLogger("test.notification.consumer")


@pytest.fixture
def reset_password_use_case() -> MagicMock:
    return MagicMock()


@pytest.fixture
def retry_policy() -> AsyncMock:
    policy = AsyncMock(spec=MessageRetryPolicy)
    return policy


@pytest.fixture
def consumer(
    reset_password_use_case: MagicMock,
    logger: logging.Logger,
    retry_policy: AsyncMock,
) -> RabbitMQConsumer:
    return RabbitMQConsumer(
        amqp_url="amqp://guest:guest@localhost/",
        reset_password_use_case=reset_password_use_case,
        logger=logger,
        queue_name="reset-password-stream",
        dlq_queue_name="reset-password-stream.dlq",
        retry_policy=retry_policy,
    )


def _build_message(body: bytes, *, retry_count: int = 0) -> MagicMock:
    message = MagicMock(spec=IncomingMessage)
    message.body = body
    message.headers = {"x-retry-count": retry_count}
    message.routing_key = "reset-password-stream"
    message.ack = AsyncMock()
    return message


@pytest.fixture
def channel() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def dlq() -> MagicMock:
    queue = MagicMock()
    queue.name = "reset-password-stream.dlq"
    return queue


@pytest.mark.asyncio
async def test_acks_on_successful_processing(
    consumer: RabbitMQConsumer,
    reset_password_use_case: MagicMock,
    channel: AsyncMock,
    dlq: MagicMock,
    sample_reset_password_payload: dict,
) -> None:
    message = _build_message(json.dumps(sample_reset_password_payload).encode())

    with patch("src.adapters.inbound.rabbitmq_consumer.asyncio.to_thread", new_callable=AsyncMock) as to_thread:
        to_thread.return_value = None
        await consumer._process_message(message, channel, dlq)

    to_thread.assert_awaited_once_with(reset_password_use_case, sample_reset_password_payload)
    message.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_sends_invalid_json_to_dlq(
    consumer: RabbitMQConsumer,
    retry_policy: AsyncMock,
    channel: AsyncMock,
    dlq: MagicMock,
) -> None:
    message = _build_message(b"not-json")

    await consumer._process_message(message, channel, dlq)

    retry_policy.send_to_dlq.assert_awaited_once()
    assert retry_policy.send_to_dlq.await_args.kwargs["reason"] == "invalid_json"
    message.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_does_not_call_use_case_on_invalid_json(
    consumer: RabbitMQConsumer,
    reset_password_use_case: MagicMock,
    channel: AsyncMock,
    dlq: MagicMock,
) -> None:
    message = _build_message(b"not-json")

    with patch("src.adapters.inbound.rabbitmq_consumer.asyncio.to_thread", new_callable=AsyncMock) as to_thread:
        await consumer._process_message(message, channel, dlq)

    to_thread.assert_not_awaited()
    reset_password_use_case.assert_not_called()


@pytest.mark.asyncio
async def test_sends_validation_error_to_dlq(
    logger: logging.Logger,
    retry_policy: AsyncMock,
    channel: AsyncMock,
    dlq: MagicMock,
) -> None:
    use_case = ResetPasswordUseCase(MagicMock(), MagicMock())
    consumer = RabbitMQConsumer(
        amqp_url="amqp://guest:guest@localhost/",
        reset_password_use_case=use_case,
        logger=logger,
        queue_name="reset-password-stream",
        dlq_queue_name="reset-password-stream.dlq",
        retry_policy=retry_policy,
    )
    message = _build_message(json.dumps({"user_id": "550e8400-e29b-41d4-a716-446655440000"}).encode())

    async def run_sync(fn, data):
        return fn(data)

    with patch("src.adapters.inbound.rabbitmq_consumer.asyncio.to_thread", side_effect=run_sync):
        await consumer._process_message(message, channel, dlq)

    retry_policy.send_to_dlq.assert_awaited_once()
    assert retry_policy.send_to_dlq.await_args.kwargs["reason"] == "validation_error"
    message.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_sends_not_sent_error_to_dlq(
    consumer: RabbitMQConsumer,
    reset_password_use_case: MagicMock,
    retry_policy: AsyncMock,
    channel: AsyncMock,
    dlq: MagicMock,
    sample_reset_password_payload: dict,
) -> None:
    message = _build_message(json.dumps(sample_reset_password_payload).encode())

    with patch("src.adapters.inbound.rabbitmq_consumer.asyncio.to_thread", new_callable=AsyncMock) as to_thread:
        to_thread.side_effect = NotSentError(recipient="user@example.com", attempts=5)
        await consumer._process_message(message, channel, dlq)

    retry_policy.send_to_dlq.assert_awaited_once()
    assert retry_policy.send_to_dlq.await_args.kwargs["reason"] == "email_send_failed"
    message.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_retries_unknown_error_with_backoff(
    consumer: RabbitMQConsumer,
    retry_policy: AsyncMock,
    channel: AsyncMock,
    dlq: MagicMock,
    sample_reset_password_payload: dict,
) -> None:
    message = _build_message(json.dumps(sample_reset_password_payload).encode(), retry_count=0)

    with patch("src.adapters.inbound.rabbitmq_consumer.asyncio.to_thread", new_callable=AsyncMock) as to_thread:
        to_thread.side_effect = RuntimeError("temporary failure")
        await consumer._process_message(message, channel, dlq)

    retry_policy.republish_with_retry.assert_awaited_once_with(channel, message, 1)
    retry_policy.send_to_dlq.assert_not_awaited()
    message.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_sends_unknown_error_to_dlq_after_max_retries(
    consumer: RabbitMQConsumer,
    retry_policy: AsyncMock,
    channel: AsyncMock,
    dlq: MagicMock,
    sample_reset_password_payload: dict,
) -> None:
    message = _build_message(json.dumps(sample_reset_password_payload).encode(), retry_count=3)

    with patch("src.adapters.inbound.rabbitmq_consumer.asyncio.to_thread", new_callable=AsyncMock) as to_thread:
        to_thread.side_effect = RuntimeError("persistent failure")
        await consumer._process_message(message, channel, dlq)

    retry_policy.republish_with_retry.assert_not_awaited()
    retry_policy.send_to_dlq.assert_awaited_once()
    assert retry_policy.send_to_dlq.await_args.kwargs["reason"] == "unknown_error"
    message.ack.assert_awaited_once()
