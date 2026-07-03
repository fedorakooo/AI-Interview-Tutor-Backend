import asyncio
import json
import logging

from aio_pika import IncomingMessage, connect_robust
from aio_pika.abc import AbstractChannel, AbstractQueue, AbstractRobustConnection
from pydantic import ValidationError
from shared_models.messaging.retry_policy import MAX_RETRIES, MessageRetryPolicy, get_retry_count

from src.config import settings
from src.domain.adapters.inbound.rabbitmq_consumer import IRabbitMQConsumer
from src.domain.errors.cv_analysis import CVAnalysisError
from src.use_cases.cv_analyze_use_case import CVAnalyzeUseCase


class RabbitMQConsumer(IRabbitMQConsumer):
    def __init__(
        self,
        amqp_url: str,
        logger: logging.Logger,
        cv_analyze_use_case: CVAnalyzeUseCase,
        retry_policy: MessageRetryPolicy | None = None,
    ):
        self.amqp_url = amqp_url
        self.logger = logger
        self.cv_analyze_use_case = cv_analyze_use_case
        self.retry_policy = retry_policy or MessageRetryPolicy()
        self.connection: AbstractRobustConnection | None = None

    async def process_messages(self) -> None:
        self.connection = await connect_robust(self.amqp_url)
        async with self.connection:
            channel = await self.connection.channel()
            await channel.set_qos(prefetch_count=3)

            dlq = await channel.declare_queue(
                settings.rabbitmq_settings.cv_analyzer_dlq_queue_name,
                durable=True,
            )
            cv_queue = await channel.declare_queue(settings.rabbitmq_settings.cv_analyzer_queue_name, durable=True)

            async def on_message(message: IncomingMessage) -> None:
                await self._process_message(message, channel, dlq)

            await cv_queue.consume(on_message)

            self.logger.info("All consumers started. Waiting for messages...")
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
        queue_name = message.routing_key or settings.rabbitmq_settings.cv_analyzer_queue_name
        retry_count = get_retry_count(message.headers)

        try:
            event_data = json.loads(message.body.decode())
            self.logger.info("Processing message from queue: %s", queue_name)

            if queue_name == settings.rabbitmq_settings.cv_analyzer_queue_name:
                await self.cv_analyze_use_case(event_data)
            else:
                self.logger.warning("No handler for queue %s", queue_name)

            await message.ack()
            self.logger.info("Successfully processed message from queue: %s", queue_name)
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
            self.logger.error("Invalid CV job payload: %s", exc)
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
        except CVAnalysisError as exc:
            if exc.retryable and retry_count < MAX_RETRIES:
                self.logger.warning(
                    "Retryable CV analysis error (%s), attempt %s/%s",
                    exc.code,
                    retry_count + 1,
                    MAX_RETRIES,
                )
                await self.retry_policy.republish_with_retry(channel, message, retry_count + 1)
                await message.ack()
                return

            if exc.retryable:
                await self.retry_policy.send_to_dlq(
                    channel,
                    dlq.name,
                    message.body,
                    reason=exc.code,
                    original_queue=queue_name,
                    retry_count=retry_count,
                    logger=self.logger,
                )
            await message.ack()
        except Exception as exc:
            self.logger.error("Error processing message from queue %s: %s", queue_name, exc, exc_info=True)
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
