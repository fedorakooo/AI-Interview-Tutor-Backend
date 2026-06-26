from abc import ABC, abstractmethod
from typing import Any


class IMongoRepository(ABC):
    """Interface defining the interface for interacting with MongoDB."""

    @abstractmethod
    async def find_one(self, id: str) -> dict[str, Any] | None:
        """Gets a document by id"""
        pass

    @abstractmethod
    async def find_latest_by_field(self, field_name: str, field_value: str) -> dict[str, Any] | None:
        """Gets the latest document matching a field value."""
        pass

    @abstractmethod
    async def insert_one(self, data: dict[str, Any]) -> str:
        """Inserts document and returns inserted id"""
        pass

    @abstractmethod
    async def update_one(
        self,
        id: str,
        update_data: dict[str, Any],
    ) -> bool:
        """Update document by ID"""
        pass

    @abstractmethod
    async def delete_one(self, id: str) -> bool:
        """Delete document by ID"""
        pass

    @abstractmethod
    async def __aenter__(self) -> "IMongoRepository":
        pass

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
