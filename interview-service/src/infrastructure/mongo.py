from typing import Any

from bson import ObjectId
from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorClientSession,
    AsyncIOMotorCollection,
)

from src.domain.interfaces.mongo import IMongoRepository


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

    async def find_latest_by_field(
        self,
        field_name: str,
        field_value: str,
        extra_filter: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        query: dict[str, Any] = {field_name: field_value}
        if extra_filter:
            query.update(extra_filter)
        return await self.collection.find_one(
            query,
            sort=[("published_at", -1)],
        )

    async def find_one_by_field(self, field_name: str, field_value: str) -> dict[str, Any] | None:
        return await self.collection.find_one({field_name: field_value})

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
        cursor = (
            self.collection.find({field_name: field_value})
            .sort(sort_field, sort_direction)
            .skip(skip)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    async def insert_one(self, data: dict[str, Any]) -> str:
        result = await self.collection.insert_one(data)
        return str(result.inserted_id)

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

    async def update_one_by_field(
        self,
        field_name: str,
        field_value: str,
        update_data: dict[str, Any],
    ) -> bool:
        result = await self.collection.update_one(
            {field_name: field_value},
            {"$set": update_data},
        )
        return result.modified_count > 0 or result.matched_count > 0

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
