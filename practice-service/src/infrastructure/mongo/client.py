from typing import Any, Protocol

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection


class IMongoCollection(Protocol):
    """Structural typing port for Motor collection operations used in repositories."""

    async def find_one(self, filter: dict[str, Any], *args: Any, **kwargs: Any) -> dict[str, Any] | None:
        """Return the first document matching the filter, or None."""
        pass

    async def insert_one(self, document: dict[str, Any]) -> Any:
        """Insert a single document into the collection."""
        pass

    async def update_one(self, filter: dict[str, Any], update: dict[str, Any], **kwargs: Any) -> Any:
        """Update the first document matching the filter."""
        pass

    async def find(self, filter: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
        """Return a cursor for documents matching the filter."""
        pass

    async def create_index(self, keys: Any, **kwargs: Any) -> str:
        """Create an index on the collection and return its name."""
        pass


class MongoClientFactory:
    @staticmethod
    def create(url: str) -> AsyncIOMotorClient:
        return AsyncIOMotorClient(url)

    @staticmethod
    def get_collection(client: AsyncIOMotorClient, db_name: str, collection_name: str) -> AsyncIOMotorCollection:
        return client[db_name][collection_name]
