from functools import lru_cache

from redis.asyncio import Redis
from src.config import settings


@lru_cache
def create_redis_client() -> Redis:
    return Redis(
        host=settings.redis_settings.host,
        port=settings.redis_settings.port,
        username=settings.redis_settings.user,
        password=settings.redis_settings.password,
        decode_responses=settings.redis_settings.decode_responses,
    )
