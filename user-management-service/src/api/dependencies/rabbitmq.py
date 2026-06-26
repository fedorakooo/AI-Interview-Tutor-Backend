from functools import lru_cache

from src.config import settings
from src.domain.interfaces.rabbitmq.rabbitmq_producer import IRabbitMQProducer
from src.infrastructure.rabbitmq.rabbitmq_producer import RabbitMQProducer


@lru_cache
def get_reset_password_producer() -> IRabbitMQProducer:
    return RabbitMQProducer(
        amqp_url=settings.rabbitmq_settings.url,
        queue_name=settings.rabbitmq_settings.reset_password_queue_name,
    )


@lru_cache
def get_cv_analyzer_producer() -> IRabbitMQProducer:
    return RabbitMQProducer(
        amqp_url=settings.rabbitmq_settings.url,
        queue_name=settings.rabbitmq_settings.cv_analyzer_queue_name,
    )
