from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError
from shared_models.assessment import AssessmentCompleted

from src.domain.interfaces.completion_outbox import ICompletionOutbox


class MongoCompletionOutbox(ICompletionOutbox):
    def __init__(self, collection: AsyncIOMotorCollection) -> None:
        self._collection = collection

    async def ensure_indexes(self) -> None:
        await self._collection.create_index("event_id", unique=True)
        await self._collection.create_index([("published", ASCENDING), ("created_at", ASCENDING)])

    async def enqueue(self, event: AssessmentCompleted) -> None:
        document = {
            "event_id": str(event.event_id),
            "payload": event.model_dump(mode="json"),
            "published": False,
            "created_at": event.occurred_at,
        }
        try:
            await self._collection.insert_one(document)
        except DuplicateKeyError:
            return

    async def list_pending(self, limit: int) -> list[AssessmentCompleted]:
        cursor = self._collection.find({"published": False}, {"_id": 0}).sort("created_at", ASCENDING)
        documents = await cursor.to_list(length=limit)
        return [AssessmentCompleted.model_validate(document["payload"]) for document in documents]

    async def mark_published(self, event_id: UUID) -> None:
        await self._collection.update_one({"event_id": str(event_id)}, {"$set": {"published": True}})
