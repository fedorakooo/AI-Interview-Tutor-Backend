import json
from logging import Logger

from pika import BlockingConnection, ConnectionParameters
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic, BasicProperties

from src.application.use_cases.reset_password_use_case import ResetPasswordUseCase
from src.domain.ports.inbound.abstract_message_broker_consumer import MessageBrokerPort


class RabbitMQConsumer(MessageBrokerPort):
    def __init__(
        self,
        connection_parameters: ConnectionParameters,
        reset_password_use_case: ResetPasswordUseCase,
        logger: Logger,
    ):
        self.connection_parameters = connection_parameters
        self.reset_password_use_case = reset_password_use_case
        self.logger = logger

    def process_messages(self) -> None:
        with BlockingConnection(self.connection_parameters) as connection:
            with connection.channel() as channel:
                channel.basic_qos(prefetch_count=5)

                channel.queue_declare(queue="reset-password-stream", durable=True)

                consumer_tag = channel.basic_consume(
                    queue="reset-password-stream",
                    on_message_callback=self._handle_message,
                )

                try:
                    channel.start_consuming()
                except KeyboardInterrupt:
                    channel.basic_cancel(consumer_tag)
                    connection.close()

    def _handle_message(
        self, channel: BlockingChannel, method: Basic.Deliver, properties: BasicProperties, body: bytes
    ) -> None:
        try:
            event_data = json.loads(body.decode())
            self.reset_password_use_case(event_data)
            channel.basic_ack(method.delivery_tag)
            self.logger.info(f"Received message from {event_data['email']}")
        except Exception as exc:
            self.logger.error(
                f"Error processing message with delivery_tag: {method.delivery_tag}. Exception: {exc}", exc_info=True
            )
            try:
                channel.basic_nack(method.delivery_tag, requeue=False)
            except Exception as nack_exc:
                self.logger.error(
                    f"Failed to NACK message with delivery_tag: {method.delivery_tag}. Nack Exception: {nack_exc}",
                    exc_info=True,
                )
