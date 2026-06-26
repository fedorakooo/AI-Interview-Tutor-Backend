import aio_pika
from aio_pika import DeliveryMode, Message

from src.domain.interfaces.rabbitmq.rabbitmq_producer import IRabbitMQProducer


class RabbitMQProducer(IRabbitMQProducer):
    def __init__(self, amqp_url: str, queue_name: str):
        self.amqp_url = amqp_url
        self.queue_name = queue_name

    async def send_message(self, message: str) -> None:
        connection = await aio_pika.connect_robust(self.amqp_url)
        async with connection:
            channel = await connection.channel()
            await channel.declare_queue(self.queue_name, durable=True)
            await channel.default_exchange.publish(
                Message(body=message.encode(), delivery_mode=DeliveryMode.PERSISTENT),
                routing_key=self.queue_name,
            )
