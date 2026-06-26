from abc import ABC, abstractmethod
from typing import Any


class AbstractMongoRepository(ABC):
    """Abstract class defining the interface for interacting with MongoDB."""

    @abstractmethod
    def find_one(self, id: str) -> dict[str, Any] | None:
        """Gets document by id"""
        pass

    @abstractmethod
    def insert_one(self, data: dict[str, Any]) -> str:
        """Inserts document and returns inserted id"""
        pass

    @abstractmethod
    def update_one(
        self,
        id: str,
        update_data: dict[str, Any],
    ) -> bool:
        """Update document by ID"""
        pass

    @abstractmethod
    def delete(self, id: str) -> bool:
        """Delete document by ID"""
        pass

    @abstractmethod
    def __enter__(self) -> "AbstractMongoRepository":
        pass

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
