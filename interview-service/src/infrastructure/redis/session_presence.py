from uuid import uuid4

from redis.asyncio import Redis
from src.domain.interfaces.session.session_presence import ISessionPresence

RELEASE_SCRIPT = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"


class SessionPresence(ISessionPresence):
    def __init__(self, client: Redis, ttl_seconds: int = 6 * 3600) -> None:
        self._client = client
        self._ttl_seconds = ttl_seconds

    async def claim(self, session_id: str) -> str:
        token = uuid4().hex
        await self._client.set(f"interview:presence:{session_id}", token, ex=self._ttl_seconds)
        return token

    async def release(self, session_id: str, token: str) -> bool:
        return bool(await self._client.eval(RELEASE_SCRIPT, 1, f"interview:presence:{session_id}", token))
