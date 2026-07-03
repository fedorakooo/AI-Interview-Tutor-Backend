from dependency_injector.containers import DeclarativeContainer
from dependency_injector.providers import DependenciesContainer, Dependency, Factory

from src.adapters.inbound.rabbitmq_consumer import RabbitMQConsumer
from src.config import settings


class InboundAdaptersContainer(DeclarativeContainer):
    use_cases = DependenciesContainer()
    logger = Dependency()

    message_broker_consumer = Factory(
        RabbitMQConsumer,
        amqp_url=settings.rabbitmq_settings.url,
        reset_password_use_case=use_cases.reset_password_use_case,
        logger=logger,
        queue_name=settings.rabbitmq_settings.reset_password_queue_name,
        dlq_queue_name=settings.rabbitmq_settings.reset_password_dlq_queue_name,
    )
