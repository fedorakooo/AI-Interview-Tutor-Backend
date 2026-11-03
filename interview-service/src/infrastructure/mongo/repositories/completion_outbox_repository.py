from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError, PyMongoError
from shared_models.assessment import AssessmentCompleted

from src.domain.exceptions.dependency_errors import DependencyUnavailableError
from src.domain.interfaces.completion_outbox_repository import ICompletionOutboxRepository


class CompletionOutboxRepository(ICompletionOutboxRepository):
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
        except PyMongoError as exc:
            raise DependencyUnavailableError() from exc

    async def list_pending(self, limit: int) -> list[AssessmentCompleted]:
        cursor = self._collection.find({"published": False}, {"_id": 0}).sort("created_at", ASCENDING)
        try:
            documents = await cursor.to_list(length=limit)
        except PyMongoError as exc:
            raise DependencyUnavailableError() from exc
        return [AssessmentCompleted.model_validate(document["payload"]) for document in documents]

    async def mark_published(self, event_id: UUID) -> None:
        try:
            await self._collection.update_one({"event_id": str(event_id)}, {"$set": {"published": True}})
        except PyMongoError as exc:
            raise DependencyUnavailableError() from exc
