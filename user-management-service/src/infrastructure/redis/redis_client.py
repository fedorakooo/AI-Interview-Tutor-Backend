from redis.asyncio import Redis

from src.domain.interfaces.redis.redis_client import IRedisClient


class RedisClient(IRedisClient):
    def __init__(self, redis: Redis):
        self.redis = redis

    async def set(self, key: str, value: str) -> bool:
        return await self.redis.set(key, value)

    async def get(self, key: str) -> str | None:
        return await self.redis.get(key)

    async def setex(self, key: str, time: int, value: str) -> bool:
        return await self.redis.setex(key, time, value)

    async def exists(self, key: str) -> bool:
        return await self.redis.exists(key) == 1

    async def delete(self, key: str) -> bool:
        return await self.redis.delete(key)
