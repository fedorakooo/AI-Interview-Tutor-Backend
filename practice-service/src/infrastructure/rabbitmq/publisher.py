import aio_pika
from aio_pika import DeliveryMode, Message
from src.domain.interfaces.message_publisher import IMessagePublisher


class RabbitMQPublisher(IMessagePublisher):
    def __init__(self, amqp_url: str) -> None:
        self.amqp_url = amqp_url

    async def publish(self, queue_name: str, message: str) -> None:
        connection = await aio_pika.connect_robust(self.amqp_url)
        async with connection:
            channel = await connection.channel()
            await channel.declare_queue(queue_name, durable=True)
            await channel.default_exchange.publish(
                Message(body=message.encode(), delivery_mode=DeliveryMode.PERSISTENT),
                routing_key=queue_name,
            )
