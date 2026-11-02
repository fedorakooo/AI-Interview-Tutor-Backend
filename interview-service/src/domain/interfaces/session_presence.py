from abc import ABC, abstractmethod


class ISessionPresence(ABC):
    @abstractmethod
    async def claim(self, session_id: str) -> str:
        """Register a new live connection of a session and return its token."""

    @abstractmethod
    async def release(self, session_id: str, token: str) -> bool:
        """Release the connection and report whether it was still the latest one."""
