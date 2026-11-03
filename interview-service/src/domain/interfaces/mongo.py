from abc import ABC, abstractmethod
from typing import Any


class IMongoRepository(ABC):
    """Generic port for document operations on one MongoDB collection."""

    @abstractmethod
    async def find_one(self, id: str) -> dict[str, Any] | None:
        """Get a document by id."""

    @abstractmethod
    async def find_latest_by_field(
        self,
        field_name: str,
        field_value: str,
        extra_filter: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Get the latest document matching a field value."""

    @abstractmethod
    async def find_one_by_field(self, field_name: str, field_value: str) -> dict[str, Any] | None:
        """Get a document by an arbitrary field value."""

    @abstractmethod
    async def find_many_by_field(
        self,
        field_name: str,
        field_value: str,
        *,
        skip: int = 0,
        limit: int = 20,
        sort_field: str = "started_at",
        sort_direction: int = -1,
    ) -> list[dict[str, Any]]:
        """Get documents matching a field value with pagination."""

    @abstractmethod
    async def insert_one(self, data: dict[str, Any]) -> str:
        """Insert a document and return its id."""

    @abstractmethod
    async def update_one(
        self,
        id: str,
        update_data: dict[str, Any],
    ) -> bool:
        """Update a document by id."""

    @abstractmethod
    async def update_one_by_field(
        self,
        field_name: str,
        field_value: str,
        update_data: dict[str, Any],
    ) -> bool:
        """Update a document by an arbitrary field value."""

    @abstractmethod
    async def delete_one(self, id: str) -> bool:
        """Delete a document by id."""

    @abstractmethod
    async def __aenter__(self) -> "IMongoRepository":
        """Start a transaction."""

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Commit the transaction, or abort it when the block raised."""
