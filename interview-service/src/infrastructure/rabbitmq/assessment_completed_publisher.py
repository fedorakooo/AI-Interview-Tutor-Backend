import asyncio

import aio_pika
from aio_pika import DeliveryMode, Message
from aio_pika.abc import AbstractChannel, AbstractRobustConnection
from shared_models.assessment import AssessmentCompleted

from src.domain.interfaces.assessment_completed_publisher import IAssessmentCompletedPublisher


class AssessmentCompletedPublisher(IAssessmentCompletedPublisher):
    def __init__(self, amqp_url: str, queue_name: str) -> None:
        self._amqp_url = amqp_url
        self._queue_name = queue_name
        self._connection: AbstractRobustConnection | None = None
        self._channel: AbstractChannel | None = None
        self._lock = asyncio.Lock()

    async def publish(self, event: AssessmentCompleted) -> None:
        channel = await self._get_channel()
        await channel.default_exchange.publish(
            Message(body=event.model_dump_json().encode(), delivery_mode=DeliveryMode.PERSISTENT),
            routing_key=self._queue_name,
        )

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
        self._connection = None
        self._channel = None

    async def _get_channel(self) -> AbstractChannel:
        async with self._lock:
            if self._connection is None or self._connection.is_closed:
                self._connection = await aio_pika.connect_robust(self._amqp_url)
                self._channel = None
            if self._channel is None or self._channel.is_closed:
                self._channel = await self._connection.channel()
                await self._channel.declare_queue(self._queue_name, durable=True)
            return self._channel
