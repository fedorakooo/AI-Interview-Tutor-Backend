import asyncio
import logging
from typing import Any

from aio_pika import DeliveryMode, IncomingMessage, Message
from aio_pika.abc import AbstractChannel

MAX_RETRIES = 3
RETRY_HEADER = "x-retry-count"
DLQ_REASON_HEADER = "x-dead-letter-reason"
DLQ_ORIGINAL_QUEUE_HEADER = "x-original-queue"
DLQ_ALERT_MARKER = "DLQ_ALERT"
BASE_RETRY_DELAY_SECONDS = 1.0
MAX_RETRY_DELAY_SECONDS = 30.0


def get_retry_count(headers: dict[str, Any] | None) -> int:
    if not headers:
        return 0

    raw_count = headers.get(RETRY_HEADER, 0)
    try:
        return int(raw_count)
    except (TypeError, ValueError):
        return 0


def compute_backoff_delay(retry_count: int) -> float:
    if retry_count <= 0:
        return 0.0

    delay = BASE_RETRY_DELAY_SECONDS * (2 ** (retry_count - 1))
    return min(delay, MAX_RETRY_DELAY_SECONDS)


class MessageRetryPolicy:
    """Shared RabbitMQ retry and dead-letter queue policy for async consumers."""

    async def republish_with_retry(
        self,
        channel: AbstractChannel,
        message: IncomingMessage,
        retry_count: int,
    ) -> None:
        delay = compute_backoff_delay(retry_count)
        if delay > 0:
            await asyncio.sleep(delay)

        headers = dict(message.headers or {})
        headers[RETRY_HEADER] = retry_count
        await channel.default_exchange.publish(
            Message(
                body=message.body,
                headers=headers,
                delivery_mode=message.delivery_mode or DeliveryMode.PERSISTENT,
            ),
            routing_key=message.routing_key or "",
        )

    async def send_to_dlq(
        self,
        channel: AbstractChannel,
        dlq_name: str,
        body: bytes,
        *,
        reason: str,
        original_queue: str,
        retry_count: int,
        logger: logging.Logger,
    ) -> None:
        await channel.default_exchange.publish(
            Message(
                body=body,
                headers={
                    DLQ_REASON_HEADER: reason,
                    DLQ_ORIGINAL_QUEUE_HEADER: original_queue,
                    RETRY_HEADER: retry_count,
                },
                delivery_mode=DeliveryMode.PERSISTENT,
            ),
            routing_key=dlq_name,
        )
        logger.error(
            "%s message sent to DLQ queue=%s reason=%s original_queue=%s retry_count=%s",
            DLQ_ALERT_MARKER,
            dlq_name,
            reason,
            original_queue,
            retry_count,
        )
