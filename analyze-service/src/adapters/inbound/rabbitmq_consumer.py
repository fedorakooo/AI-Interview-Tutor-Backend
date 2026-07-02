import asyncio
import json
import logging

from aio_pika import IncomingMessage, connect_robust
from aio_pika.abc import AbstractRobustConnection

from src.config import settings
from src.domain.adapters.inbound.rabbitmq_consumer import IRabbitMQConsumer
from src.use_cases.cv_analyze_use_case import CVAnalyzeUseCase


class RabbitMQConsumer(IRabbitMQConsumer):
    def __init__(
        self,
        amqp_url: str,
        logger: logging.Logger,
        cv_analyze_use_case: CVAnalyzeUseCase,
    ):
        self.amqp_url = amqp_url
        self.logger = logger
        self.cv_analyze_use_case = cv_analyze_use_case
        self.connection: AbstractRobustConnection | None = None

    async def process_messages(self) -> None:
        self.connection = await connect_robust(self.amqp_url)
        async with self.connection:
            channel = await self.connection.channel()
            await channel.set_qos(prefetch_count=3)

            cv_queue = await channel.declare_queue(settings.rabbitmq_settings.cv_analyzer_queue_name, durable=True)

            await cv_queue.consume(self._handle_message)

            self.logger.info("All consumers started. Waiting for messages...")
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                self.logger.info("Consumer cancelled, shutting down gracefully...")

    async def _handle_message(self, message: IncomingMessage) -> None:
        """
        Handles a single message and routes to the right use case
        depending on the queue name.
        """
        async with message.process(requeue=False):
            try:
                event_data = json.loads(message.body.decode())
                queue_name = message.routing_key

                self.logger.info(f"Processing message from queue: {queue_name}")

                if queue_name == settings.rabbitmq_settings.cv_analyzer_queue_name:
                    await self.cv_analyze_use_case(event_data)
                else:
                    self.logger.warning(f"No handler for queue {queue_name}")

                self.logger.info(f"Successfully processed message from queue: {queue_name}")

            except json.JSONDecodeError as exc:
                self.logger.error(f"Failed to decode JSON from message. Body: {message.body!r}. Error: {exc}")
            except Exception as exc:
                self.logger.error(f"Error processing message from queue {message.routing_key}: {exc}", exc_info=True)
