from typing import Any

from bson import ObjectId
from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorClientSession,
    AsyncIOMotorCollection,
)

from src.domain.adapters.outbound.mongo import IMongoRepository


class MongoRepository(IMongoRepository):
    """Repository for MongoDB operations using motor."""

    def __init__(
        self,
        client: AsyncIOMotorClient,
        db_name: str,
        collection_name: str,
    ):
        self._client = client
        self.collection: AsyncIOMotorCollection = client[db_name][collection_name]
        self._session: AsyncIOMotorClientSession | None = None

    async def find_one(self, id: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"_id": ObjectId(id)})

    async def insert_one(self, data: dict[str, Any]) -> str:
        result = await self.collection.insert_one(data)
        return str(result.inserted_id)

    async def upsert_by_correlation_id(self, correlation_id: str, document: dict[str, Any]) -> str:
        result = await self.collection.update_one(
            {"correlation_id": correlation_id},
            {"$set": document},
            upsert=True,
        )
        if result.upserted_id is not None:
            return str(result.upserted_id)

        existing = await self.collection.find_one({"correlation_id": correlation_id}, {"_id": 1})
        if existing is None:
            raise RuntimeError(f"Failed to resolve Mongo document id for correlation_id={correlation_id}")
        return str(existing["_id"])

    async def ensure_indexes(self) -> None:
        await self.collection.create_index("correlation_id", unique=True)
        await self.collection.create_index([("user_id", 1), ("published_at", -1)])

    async def update_one(
        self,
        id: str,
        update_data: dict[str, Any],
    ) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(id)},
            {"$set": update_data},
        )
        return result.modified_count > 0

    async def delete_one(self, id: str) -> bool:
        result = await self.collection.delete_one({"_id": ObjectId(id)})
        return result.deleted_count > 0

    async def __aenter__(self) -> "MongoRepository":
        self._session = await self._client.start_session()
        self._session.start_transaction()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            if exc_type is None:
                await self._session.commit_transaction()
            else:
                await self._session.abort_transaction()
            await self._session.end_session()
            self._session = None
