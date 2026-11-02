import aio_pika
from aio_pika import DeliveryMode, Message
from shared_models.assessment import AssessmentCompleted

from src.domain.interfaces.assessment_completed_publisher import IAssessmentCompletedPublisher


class AssessmentCompletedPublisher(IAssessmentCompletedPublisher):
    def __init__(self, amqp_url: str, queue_name: str) -> None:
        self._amqp_url = amqp_url
        self._queue_name = queue_name

    async def publish(self, event: AssessmentCompleted) -> None:
        connection = await aio_pika.connect_robust(self._amqp_url)
        async with connection:
            channel = await connection.channel()
            await channel.declare_queue(self._queue_name, durable=True)
            await channel.default_exchange.publish(
                Message(body=event.model_dump_json().encode(), delivery_mode=DeliveryMode.PERSISTENT),
                routing_key=self._queue_name,
            )
