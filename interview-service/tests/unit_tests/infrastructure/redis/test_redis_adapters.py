import pytest
from redis.exceptions import RedisError
from src.domain.exceptions.dependency_errors import DependencyUnavailableError
from src.domain.exceptions.session_errors import SessionBusyError
from src.infrastructure.redis.session_lock import SessionLock
from src.infrastructure.redis.session_presence import SessionPresence


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def set(self, key: str, value: str, nx: bool = False, px: int | None = None, ex: int | None = None) -> bool:
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def eval(self, script: str, numkeys: int, key: str, token: str) -> int:
        if self.values.get(key) == token:
            del self.values[key]
            return 1
        return 0


class BrokenRedis:
    async def set(self, *args, **kwargs) -> bool:
        raise RedisError("down")


async def test_lock_is_exclusive_and_released() -> None:
    redis = FakeRedis()
    lock = SessionLock(redis, wait_seconds=0.05)

    async with lock.hold("session-1"):
        with pytest.raises(SessionBusyError):
            async with lock.hold("session-1"):
                pass
        async with lock.hold("session-2"):
            pass

    async with lock.hold("session-1"):
        pass
    assert redis.values == {}


async def test_lock_is_released_when_the_body_fails() -> None:
    redis = FakeRedis()
    lock = SessionLock(redis, wait_seconds=0.05)

    with pytest.raises(RuntimeError):
        async with lock.hold("session-1"):
            raise RuntimeError("boom")

    assert redis.values == {}


async def test_presence_keeps_only_the_latest_connection_releasable() -> None:
    presence = SessionPresence(FakeRedis())

    old = await presence.claim("session-1")
    new = await presence.claim("session-1")

    assert await presence.release("session-1", old) is False
    assert await presence.release("session-1", new) is True
    assert await presence.release("session-1", new) is False


async def test_redis_failure_becomes_a_dependency_error() -> None:
    with pytest.raises(DependencyUnavailableError):
        async with SessionLock(BrokenRedis()).hold("session-1"):
            pass
