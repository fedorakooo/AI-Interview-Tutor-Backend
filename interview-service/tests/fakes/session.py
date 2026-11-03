from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from src.domain.exceptions.session_errors import SessionBusyError
from src.domain.interfaces.session.session_lock import ISessionLock
from src.domain.interfaces.session.session_presence import ISessionPresence


class InMemoryLock(ISessionLock):
    def __init__(self) -> None:
        self.held: set[str] = set()

    @asynccontextmanager
    async def hold(self, session_id: str) -> AsyncIterator[None]:
        if session_id in self.held:
            raise SessionBusyError()
        self.held.add(session_id)
        try:
            yield
        finally:
            self.held.discard(session_id)


class InMemoryPresence(ISessionPresence):
    def __init__(self) -> None:
        self.current: dict[str, str] = {}
        self.counter = 0

    async def claim(self, session_id: str) -> str:
        self.counter += 1
        token = f"connection-{self.counter}"
        self.current[session_id] = token
        return token

    async def release(self, session_id: str, token: str) -> bool:
        if self.current.get(session_id) == token:
            del self.current[session_id]
            return True
        return False
