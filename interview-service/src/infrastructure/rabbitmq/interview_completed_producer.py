import aio_pika
from aio_pika import DeliveryMode, Message
from shared_models.practice.messaging import InterviewCompletedEvent


class InterviewCompletedProducer:
    def __init__(self, amqp_url: str, queue_name: str) -> None:
        self.amqp_url = amqp_url
        self.queue_name = queue_name

    async def publish(self, event: InterviewCompletedEvent) -> None:
        connection = await aio_pika.connect_robust(self.amqp_url)
        async with connection:
            channel = await connection.channel()
            await channel.declare_queue(self.queue_name, durable=True)
            await channel.default_exchange.publish(
                Message(body=event.model_dump_json().encode(), delivery_mode=DeliveryMode.PERSISTENT),
                routing_key=self.queue_name,
            )
