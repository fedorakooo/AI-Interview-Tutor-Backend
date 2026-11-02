from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorCollection

from src.domain.interfaces.attempt_data_repository import IAttemptDataRepository


class AttemptDataRepository(IAttemptDataRepository):
    def __init__(
        self,
        events: AsyncIOMotorCollection,
        assessments: AsyncIOMotorCollection,
        reviews: AsyncIOMotorCollection,
        feedback: AsyncIOMotorCollection,
        cv_documents: AsyncIOMotorCollection,
    ) -> None:
        self._events = events
        self._assessments = assessments
        self._reviews = reviews
        self._feedback = feedback
        self._cv_documents = cv_documents

    async def erase(self, attempt_id: UUID, cv_correlation_id: UUID | None) -> dict[str, int]:
        key = str(attempt_id)
        deleted = {
            "events": (await self._events.delete_many({"session_id": key})).deleted_count,
            "assessments": (await self._assessments.delete_many({"attempt_id": key})).deleted_count,
            "reviews": (await self._reviews.delete_many({"attempt_id": key})).deleted_count,
            "feedback": (await self._feedback.delete_many({"attempt_id": key})).deleted_count,
            "cv_documents": 0,
        }
        if cv_correlation_id is not None:
            result = await self._cv_documents.delete_many({"correlation_id": str(cv_correlation_id)})
            deleted["cv_documents"] = result.deleted_count
        return deleted
