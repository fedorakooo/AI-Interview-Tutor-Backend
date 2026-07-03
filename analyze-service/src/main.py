import asyncio
import socket
import time
from logging import Logger

from dependency_injector.wiring import Provide, inject

from src.config import settings
from src.containers.container import Container
from src.domain.adapters.inbound.rabbitmq_consumer import IRabbitMQConsumer


@inject
def wait_for_rabbitmq(
    host: str = settings.rabbitmq_settings.host,
    port: int = settings.rabbitmq_settings.port,
    timeout: float = settings.rabbitmq_settings.timeout,
    logger: Logger = Provide[Container.app_logger],
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
async def main(
    rabbitmq_consumer: IRabbitMQConsumer = Provide[Container.inbound_adapters.rabbitmq_consumer],
    mongo_repository=Provide[Container.outbound_adapters.mongo_cv_analysis_repository],
) -> None:
    wait_for_rabbitmq()
    await mongo_repository.ensure_indexes()

    await rabbitmq_consumer.process_messages()


if __name__ == "__main__":
    container = Container()
    container.wire(modules=[__name__])

    container.init_resources()

    asyncio.run(main())
