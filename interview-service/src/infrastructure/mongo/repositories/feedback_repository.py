from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo import DESCENDING
from pymongo.errors import DuplicateKeyError
from shared_models.assessment import FeedbackView

from src.domain.interfaces.feedback_repository import IFeedbackRepository


class FeedbackRepository(IFeedbackRepository):
    def __init__(self, collection: AsyncIOMotorCollection) -> None:
        self._collection = collection

    async def ensure_indexes(self) -> None:
        await self._collection.create_index([("attempt_id", DESCENDING), ("version", DESCENDING)], unique=True)

    async def latest(self, attempt_id: UUID) -> FeedbackView | None:
        cursor = self._collection.find({"attempt_id": str(attempt_id)}, {"_id": 0}).sort("version", DESCENDING)
        documents = await cursor.to_list(length=1)
        return FeedbackView.model_validate(documents[0]) if documents else None

    async def append(self, feedback: FeedbackView) -> bool:
        try:
            await self._collection.insert_one(feedback.model_dump(mode="json"))
        except DuplicateKeyError:
            return False
        return True
