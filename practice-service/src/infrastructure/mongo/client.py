from typing import Any, Protocol

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection


class IMongoCollection(Protocol):
    async def find_one(self, filter: dict[str, Any], *args: Any, **kwargs: Any) -> dict[str, Any] | None: ...

    async def insert_one(self, document: dict[str, Any]) -> Any: ...

    async def update_one(self, filter: dict[str, Any], update: dict[str, Any], **kwargs: Any) -> Any: ...

    async def find(self, filter: dict[str, Any], *args: Any, **kwargs: Any) -> Any: ...

    async def create_index(self, keys: Any, **kwargs: Any) -> str: ...


class MongoClientFactory:
    @staticmethod
    def create(url: str) -> AsyncIOMotorClient:
        return AsyncIOMotorClient(url)

    @staticmethod
    def get_collection(client: AsyncIOMotorClient, db_name: str, collection_name: str) -> AsyncIOMotorCollection:
        return client[db_name][collection_name]
