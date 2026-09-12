import asyncio
import json
import logging
from collections.abc import Callable

from aio_pika import IncomingMessage, connect_robust
from aio_pika.abc import AbstractChannel, AbstractQueue, AbstractRobustConnection
from pydantic import ValidationError
from shared_models.messaging.retry_policy import MAX_RETRIES, MessageRetryPolicy, get_retry_count

from src.application.use_cases.send_notification_email_use_case import SendNotificationEmailUseCase
from src.domain.exceptions.not_sent_error import NotSentError
from src.domain.ports.inbound.abstract_message_broker_consumer import MessageBrokerPort


class NotificationEmailConsumer(MessageBrokerPort):
    """Consumes generic notification queues (email_verify, plan_ready, welcome, interview_complete)."""

    def __init__(
        self,
        amqp_url: str,
        notification_use_case: SendNotificationEmailUseCase,
        logger: logging.Logger,
        queue_names: list[str],
        dlq_queue_names: list[str],
        retry_policy: MessageRetryPolicy | None = None,
    ):
        self.amqp_url = amqp_url
        self.notification_use_case = notification_use_case
        self.logger = logger
        self.queue_names = queue_names
        self.dlq_queue_names = dlq_queue_names
        self.retry_policy = retry_policy or MessageRetryPolicy()
        self.connection: AbstractRobustConnection | None = None

    async def process_messages(self) -> None:
        self.connection = await connect_robust(self.amqp_url)
        async with self.connection:
            channel = await self.connection.channel()
            await channel.set_qos(prefetch_count=5)

            dlqs = []
            for dlq_name in self.dlq_queue_names:
                dlqs.append(await channel.declare_queue(dlq_name, durable=True))

            for index, queue_name in enumerate(self.queue_names):
                dlq = dlqs[index] if index < len(dlqs) else dlqs[-1]
                queue = await channel.declare_queue(queue_name, durable=True)

                async def on_message(message: IncomingMessage, *, _dlq=dlq, _queue_name=queue_name) -> None:
                    await self._process_message(message, channel, _dlq, _queue_name)

                await queue.consume(on_message)
                self.logger.info("Notification consumer started on queue %s", queue_name)

            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                self.logger.info("Notification consumer cancelled")

    async def _process_message(
        self,
        message: IncomingMessage,
        channel: AbstractChannel,
        dlq: AbstractQueue,
        queue_name: str,
    ) -> None:
        retry_count = get_retry_count(message.headers)
        try:
            event_data = json.loads(message.body.decode())
            await asyncio.to_thread(self.notification_use_case, event_data)
            await message.ack()
        except (json.JSONDecodeError, ValidationError) as exc:
            self.logger.error("Invalid notification payload on %s: %s", queue_name, exc)
            await self.retry_policy.send_to_dlq(
                channel,
                dlq.name,
                message.body,
                reason="validation_error",
                original_queue=queue_name,
                retry_count=retry_count,
                logger=self.logger,
            )
            await message.ack()
        except NotSentError as exc:
            self.logger.error("Notification email send failed: %s", exc)
            await self.retry_policy.send_to_dlq(
                channel,
                dlq.name,
                message.body,
                reason="email_send_failed",
                original_queue=queue_name,
                retry_count=retry_count,
                logger=self.logger,
            )
            await message.ack()
        except Exception as exc:
            self.logger.error("Notification processing error: %s", exc, exc_info=True)
            if retry_count < MAX_RETRIES:
                await self.retry_policy.republish_with_retry(channel, message, retry_count + 1)
                await message.ack()
                return
            await self.retry_policy.send_to_dlq(
                channel,
                dlq.name,
                message.body,
                reason="unknown_error",
                original_queue=queue_name,
                retry_count=retry_count,
                logger=self.logger,
            )
            await message.ack()
