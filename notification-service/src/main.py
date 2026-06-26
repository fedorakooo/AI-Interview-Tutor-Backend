import socket
import time
from logging import Logger

from dependency_injector.wiring import Provide, inject
from pymongo import MongoClient

from src.config import settings
from src.containers.container import Container
from src.domain.ports.inbound.abstract_message_broker_consumer import MessageBrokerPort


@inject
def wait_for_rabbitmq(
    host: str = settings.rabbitmq_settings.host,
    port: int = settings.rabbitmq_settings.port,
    timeout: float = settings.rabbitmq_settings.timeout,
    logger: Logger = Provide[Container.logger],
) -> None:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                logger.info("RabbitMQ connection established")
                return
        except Exception:
            time.sleep(1.0)
            logger.info("Waiting for RabbitMQ connection")

    raise TimeoutError("RabbitMQ connection timed out")


@inject
def main(
    message_broker_consumer: MessageBrokerPort = Provide[Container.inbound_adapters.message_broker_consumer],
    mongo_client: MongoClient = Provide[Container.outbound_adapters.mongo_client],
):
    wait_for_rabbitmq()

    message_broker_consumer.process_messages()

    mongo_client.close()


if __name__ == "__main__":
    container = Container()
    container.wire(modules=[__name__])

    container.init_resources()

    main()
