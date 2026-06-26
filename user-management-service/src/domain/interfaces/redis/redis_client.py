from abc import ABC, abstractmethod


class IRedisClient(ABC):
    """Interface defining the interface for Redis client operations."""

    @abstractmethod
    async def set(self, key: str, value: str) -> bool:
        """Sets key to hold the string value."""
        pass

    @abstractmethod
    async def get(self, key: str) -> str | None:
        """Returns the value of a key."""

    @abstractmethod
    async def setex(self, key: str, time: int, value: str) -> bool:
        """
        Sets key to hold the string value and set key to timeout after given seconds.
        """
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Returns True if key exists."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Removes the specified key. Returns True if key was removed."""
        pass
