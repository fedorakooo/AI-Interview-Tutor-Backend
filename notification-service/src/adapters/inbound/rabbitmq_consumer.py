import asyncio
import json
import logging

from aio_pika import IncomingMessage, connect_robust
from aio_pika.abc import AbstractChannel, AbstractQueue, AbstractRobustConnection
from pydantic import ValidationError
from shared_models.messaging.retry_policy import MAX_RETRIES, MessageRetryPolicy, get_retry_count

from src.application.use_cases.reset_password_use_case import ResetPasswordUseCase
from src.domain.exceptions.not_sent_error import NotSentError
from src.domain.ports.inbound.abstract_message_broker_consumer import MessageBrokerPort


class RabbitMQConsumer(MessageBrokerPort):
    def __init__(
        self,
        amqp_url: str,
        reset_password_use_case: ResetPasswordUseCase,
        logger: logging.Logger,
        queue_name: str,
        dlq_queue_name: str,
        retry_policy: MessageRetryPolicy | None = None,
    ):
        self.amqp_url = amqp_url
        self.reset_password_use_case = reset_password_use_case
        self.logger = logger
        self.queue_name = queue_name
        self.dlq_queue_name = dlq_queue_name
        self.retry_policy = retry_policy or MessageRetryPolicy()
        self.connection: AbstractRobustConnection | None = None

    async def process_messages(self) -> None:
        self.connection = await connect_robust(self.amqp_url)
        async with self.connection:
            channel = await self.connection.channel()
            await channel.set_qos(prefetch_count=5)

            dlq = await channel.declare_queue(self.dlq_queue_name, durable=True)
            queue = await channel.declare_queue(self.queue_name, durable=True)

            async def on_message(message: IncomingMessage) -> None:
                await self._process_message(message, channel, dlq)

            await queue.consume(on_message)

            self.logger.info("Reset-password consumer started. Waiting for messages...")
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                self.logger.info("Consumer cancelled, shutting down gracefully...")

    async def _process_message(
        self,
        message: IncomingMessage,
        channel: AbstractChannel,
        dlq: AbstractQueue,
    ) -> None:
        queue_name = message.routing_key or self.queue_name
        retry_count = get_retry_count(message.headers)

        try:
            event_data = json.loads(message.body.decode())
            self.logger.info("Processing reset-password message from queue: %s", queue_name)
            await asyncio.to_thread(self.reset_password_use_case, event_data)
            await message.ack()
            self.logger.info("Successfully processed reset-password message")
        except json.JSONDecodeError as exc:
            self.logger.error("Failed to decode JSON from message. Body: %r. Error: %s", message.body, exc)
            await self.retry_policy.send_to_dlq(
                channel,
                dlq.name,
                message.body,
                reason="invalid_json",
                original_queue=queue_name,
                retry_count=retry_count,
                logger=self.logger,
            )
            await message.ack()
        except ValidationError as exc:
            self.logger.error("Invalid reset-password payload: %s", exc)
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
            self.logger.error("Email send failed after retries: %s", exc)
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
            self.logger.error("Error processing reset-password message: %s", exc, exc_info=True)
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
