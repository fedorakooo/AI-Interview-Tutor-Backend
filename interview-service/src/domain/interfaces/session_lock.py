from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager


class ISessionLock(ABC):
    @abstractmethod
    def hold(self, session_id: str) -> AbstractAsyncContextManager[None]:
        """Hold the exclusive turn lock of a session or raise when it is busy."""
