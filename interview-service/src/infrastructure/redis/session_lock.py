import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from redis.asyncio import Redis
from redis.exceptions import RedisError
from src.domain.exceptions.dependency_errors import DependencyUnavailableError
from src.domain.exceptions.session_errors import SessionBusyError
from src.domain.interfaces.session.session_lock import ISessionLock

RELEASE_SCRIPT = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"


class SessionLock(ISessionLock):
    def __init__(self, client: Redis, ttl_seconds: int = 120, wait_seconds: float = 2.0) -> None:
        self._client = client
        self._ttl_ms = ttl_seconds * 1000
        self._wait_seconds = wait_seconds

    @asynccontextmanager
    async def hold(self, session_id: str) -> AsyncIterator[None]:
        key = f"interview:lock:{session_id}"
        token = uuid4().hex
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._wait_seconds
        while not await self._acquire(key, token):
            if loop.time() >= deadline:
                raise SessionBusyError()
            await asyncio.sleep(0.05)
        try:
            yield
        finally:
            await self._client.eval(RELEASE_SCRIPT, 1, key, token)

    async def _acquire(self, key: str, token: str) -> bool:
        try:
            return bool(await self._client.set(key, token, nx=True, px=self._ttl_ms))
        except RedisError as exc:
            raise DependencyUnavailableError() from exc
