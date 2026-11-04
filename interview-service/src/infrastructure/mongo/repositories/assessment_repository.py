from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError

from src.domain.entities.assessment import Assessment
from src.domain.entities.review_entry import ReviewEntry
from src.domain.interfaces.repositories.assessment_repository import IAssessmentRepository
from src.infrastructure.mappers.assessment_mapper import AssessmentMapper
from src.infrastructure.mappers.review_entry_mapper import ReviewEntryMapper
from src.infrastructure.mongo.documents.assessment_document import AssessmentDocument, ReviewEntryDocument


class AssessmentRepository(IAssessmentRepository):
    def __init__(self, assessments: AsyncIOMotorCollection, reviews: AsyncIOMotorCollection) -> None:
        self._assessments = assessments
        self._reviews = reviews

    async def ensure_indexes(self) -> None:
        await self._assessments.create_index("attempt_id", unique=True)
        await self._reviews.create_index([("attempt_id", ASCENDING), ("created_at", ASCENDING)])
        await self._reviews.create_index("review_id", unique=True)

    async def get(self, attempt_id: UUID) -> Assessment | None:
        document = await self._assessments.find_one({"attempt_id": str(attempt_id)}, {"_id": 0})
        return AssessmentMapper.to_domain(AssessmentDocument.model_validate(document)) if document else None

    async def save(self, assessment: Assessment) -> None:
        try:
            await self._assessments.insert_one(
                AssessmentMapper.to_model(assessment).model_dump(
                    mode="json", exclude={"focus": {"__all__": {"review"}}}
                )
            )
        except DuplicateKeyError:
            return

    async def add_review(self, attempt_id: UUID, focus_id: str, entry: ReviewEntry) -> None:
        document = ReviewEntryMapper.to_model(entry).model_dump(mode="json")
        document.update({"attempt_id": str(attempt_id), "focus_id": focus_id, "created_at": entry.created_at})
        await self._reviews.insert_one(document)

    async def list_reviews(self, attempt_id: UUID) -> dict[str, list[ReviewEntry]]:
        cursor = self._reviews.find({"attempt_id": str(attempt_id)}, {"_id": 0}).sort("created_at", ASCENDING)
        grouped: dict[str, list[ReviewEntry]] = {}
        for document in await cursor.to_list(length=None):
            grouped.setdefault(document["focus_id"], []).append(
                ReviewEntryMapper.to_domain(ReviewEntryDocument.model_validate(document))
            )
        return grouped
