from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager


class ISessionLock(ABC):
    """Port for the exclusive turn lock of an interview session."""

    @abstractmethod
    def hold(self, session_id: str) -> AbstractAsyncContextManager[None]:
        """Hold the exclusive turn lock of a session or raise when it is busy."""
