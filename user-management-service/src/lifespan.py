import socket
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.dependencies.database import get_async_engine
from src.api.dependencies.redis import get_redis
from src.config import settings
from src.infrastructure.logger.logger import logger


def wait_for_rabbitmq(
    host: str = settings.rabbitmq_settings.host,
    port: int = settings.rabbitmq_settings.port,
    timeout: float = settings.rabbitmq_settings.timeout,
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = get_redis()
    async_engine = get_async_engine()
    wait_for_rabbitmq()

    try:
        yield
    finally:
        if redis:
            await redis.close()
        if async_engine:
            await async_engine.close()
