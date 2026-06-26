from typing import Any

from bson import ObjectId
from pymongo import MongoClient
from pymongo.collection import Collection

from src.domain.ports.outbound.abstract_mongo_repository import AbstractMongoRepository


class MongoRepository(AbstractMongoRepository):
    def __init__(self, client: MongoClient, db_name: str, collection_name: str):
        self._client = client
        self.collection: Collection = client[db_name][collection_name]

    def find_one(self, id: str) -> dict[str, Any] | None:
        return self.collection.find_one({"_id": ObjectId(id)})

    def insert_one(self, data: dict[str, Any]) -> str:
        result = self.collection.insert_one(data)
        return str(result.inserted_id)

    def update_one(
        self,
        id: str,
        update_data: dict[str, Any],
    ) -> bool:
        result = self.collection.update_one(
            {"_id": ObjectId(id)},
            {"$set": update_data},
        )
        return result.modified_count > 0

    def delete(self, id: str) -> bool:
        result = self.collection.delete_one({"_id": ObjectId(id)})
        return result.deleted_count > 0

    def __enter__(self) -> "MongoRepository":
        self._session = self._client.start_session()
        self._session.start_transaction()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            if exc_type is None:
                self._session.commit_transaction()
            else:
                self._session.abort_transaction()
            self._session.end_session()
            self._session = None
