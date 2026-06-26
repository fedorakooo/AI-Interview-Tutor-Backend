from dependency_injector.containers import DeclarativeContainer
from dependency_injector.providers import DependenciesContainer, Dependency, Factory, Singleton
from pika import ConnectionParameters, PlainCredentials

from src.adapters.inbound.rabbitmq_consumer import RabbitMQConsumer
from src.config import settings


class InboundAdaptersContainer(DeclarativeContainer):
    use_cases = DependenciesContainer()
    logger = Dependency()

    connection_parameters = Singleton(
        ConnectionParameters,
        host=settings.rabbitmq_settings.host,
        port=settings.rabbitmq_settings.port,
        credentials=PlainCredentials(
            username=settings.rabbitmq_settings.user,
            password=settings.rabbitmq_settings.password,
        ),
    )

    message_broker_consumer = Factory(
        RabbitMQConsumer,
        connection_parameters=connection_parameters,
        reset_password_use_case=use_cases.reset_password_use_case,
        logger=logger,
    )
