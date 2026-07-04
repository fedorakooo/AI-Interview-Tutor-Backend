import json
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from aio_pika import IncomingMessage
from pydantic import ValidationError
from shared_models.messaging.cv_analysis import CVAnalysisJobMessage
from shared_models.messaging.retry_policy import MessageRetryPolicy
from src.adapters.inbound.rabbitmq_consumer import RabbitMQConsumer
from src.domain.errors.cv_analysis import ExtractionQualityError, S3DownloadError


@pytest.fixture
def logger() -> logging.Logger:
    return logging.getLogger("test.analyze.consumer")


@pytest.fixture
def cv_analyze_use_case() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def retry_policy() -> AsyncMock:
    return AsyncMock(spec=MessageRetryPolicy)


@pytest.fixture
def consumer(
    cv_analyze_use_case: AsyncMock,
    logger: logging.Logger,
    retry_policy: AsyncMock,
) -> RabbitMQConsumer:
    return RabbitMQConsumer(
        amqp_url="amqp://guest:guest@localhost/",
        logger=logger,
        cv_analyze_use_case=cv_analyze_use_case,
        retry_policy=retry_policy,
    )


def _build_message(body: bytes, *, retry_count: int = 0, routing_key: str = "cv-analyze-stream") -> MagicMock:
    message = MagicMock(spec=IncomingMessage)
    message.body = body
    message.headers = {"x-retry-count": retry_count}
    message.routing_key = routing_key
    message.ack = AsyncMock()
    return message


@pytest.fixture
def channel() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def dlq() -> MagicMock:
    queue = MagicMock()
    queue.name = "cv-analyze-stream.dlq"
    return queue


@pytest.mark.asyncio
async def test_acks_on_successful_job_processing(
    consumer: RabbitMQConsumer,
    cv_analyze_use_case: AsyncMock,
    retry_policy: AsyncMock,
    channel: AsyncMock,
    dlq: MagicMock,
    job_message: CVAnalysisJobMessage,
) -> None:
    message = _build_message(json.dumps(job_message.model_dump(mode="json")).encode())

    await consumer._process_message(message, channel, dlq)

    cv_analyze_use_case.assert_awaited_once_with(job_message.model_dump(mode="json"))
    message.ack.assert_awaited_once()
    retry_policy.send_to_dlq.assert_not_awaited()
    retry_policy.republish_with_retry.assert_not_awaited()


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
async def test_sends_validation_error_to_dlq(
    consumer: RabbitMQConsumer,
    cv_analyze_use_case: AsyncMock,
    retry_policy: AsyncMock,
    channel: AsyncMock,
    dlq: MagicMock,
) -> None:
    message = _build_message(json.dumps({"user_id": "550e8400-e29b-41d4-a716-446655440000"}).encode())
    cv_analyze_use_case.side_effect = ValidationError.from_exception_data("CVAnalysisJobMessage", [])

    await consumer._process_message(message, channel, dlq)

    cv_analyze_use_case.assert_awaited_once()
    retry_policy.send_to_dlq.assert_awaited_once()
    assert retry_policy.send_to_dlq.await_args.kwargs["reason"] == "validation_error"
    message.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_retries_retryable_cv_analysis_error(
    consumer: RabbitMQConsumer,
    cv_analyze_use_case: AsyncMock,
    retry_policy: AsyncMock,
    channel: AsyncMock,
    dlq: MagicMock,
    job_message: CVAnalysisJobMessage,
) -> None:
    message = _build_message(json.dumps(job_message.model_dump(mode="json")).encode(), retry_count=0)
    cv_analyze_use_case.side_effect = S3DownloadError("network down")

    await consumer._process_message(message, channel, dlq)

    retry_policy.republish_with_retry.assert_awaited_once_with(channel, message, 1)
    retry_policy.send_to_dlq.assert_not_awaited()
    message.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_sends_retryable_error_to_dlq_after_max_retries(
    consumer: RabbitMQConsumer,
    cv_analyze_use_case: AsyncMock,
    retry_policy: AsyncMock,
    channel: AsyncMock,
    dlq: MagicMock,
    job_message: CVAnalysisJobMessage,
) -> None:
    message = _build_message(json.dumps(job_message.model_dump(mode="json")).encode(), retry_count=3)
    cv_analyze_use_case.side_effect = S3DownloadError("network down")

    await consumer._process_message(message, channel, dlq)

    retry_policy.republish_with_retry.assert_not_awaited()
    retry_policy.send_to_dlq.assert_awaited_once()
    assert retry_policy.send_to_dlq.await_args.kwargs["reason"] == "S3_DOWNLOAD_FAILED"
    message.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_acks_non_retryable_cv_analysis_error(
    consumer: RabbitMQConsumer,
    cv_analyze_use_case: AsyncMock,
    retry_policy: AsyncMock,
    channel: AsyncMock,
    dlq: MagicMock,
    job_message: CVAnalysisJobMessage,
) -> None:
    message = _build_message(json.dumps(job_message.model_dump(mode="json")).encode())
    cv_analyze_use_case.side_effect = ExtractionQualityError("too short")

    await consumer._process_message(message, channel, dlq)

    retry_policy.republish_with_retry.assert_not_awaited()
    retry_policy.send_to_dlq.assert_not_awaited()
    message.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_retries_unknown_exception(
    consumer: RabbitMQConsumer,
    cv_analyze_use_case: AsyncMock,
    retry_policy: AsyncMock,
    channel: AsyncMock,
    dlq: MagicMock,
    job_message: CVAnalysisJobMessage,
) -> None:
    message = _build_message(json.dumps(job_message.model_dump(mode="json")).encode(), retry_count=0)
    cv_analyze_use_case.side_effect = RuntimeError("unexpected")

    await consumer._process_message(message, channel, dlq)

    retry_policy.republish_with_retry.assert_awaited_once_with(channel, message, 1)
    message.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_sends_unknown_error_to_dlq_after_max_retries(
    consumer: RabbitMQConsumer,
    cv_analyze_use_case: AsyncMock,
    retry_policy: AsyncMock,
    channel: AsyncMock,
    dlq: MagicMock,
    job_message: CVAnalysisJobMessage,
) -> None:
    message = _build_message(json.dumps(job_message.model_dump(mode="json")).encode(), retry_count=3)
    cv_analyze_use_case.side_effect = RuntimeError("persistent")

    await consumer._process_message(message, channel, dlq)

    retry_policy.republish_with_retry.assert_not_awaited()
    retry_policy.send_to_dlq.assert_awaited_once()
    assert retry_policy.send_to_dlq.await_args.kwargs["reason"] == "unknown_error"
    message.ack.assert_awaited_once()
