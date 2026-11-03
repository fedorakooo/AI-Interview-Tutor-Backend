from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo import DESCENDING
from shared_models.cv.cv_data import CVData
from shared_models.messaging.common import AnalysisStatus

from src.domain.interfaces.repositories.candidate_cv_repository import ICandidateCvRepository
from src.domain.value_objects.candidate_cv import CandidateCv
from src.infrastructure.mappers.candidate_cv_mapper import CandidateCvMapper

CV_METADATA_FIELDS = {
    "_id",
    "correlation_id",
    "user_id",
    "s3_object_key",
    "source_url",
    "status",
    "published_at",
    "analyzed_at",
    "extraction_metadata",
}


class CandidateCvRepository(ICandidateCvRepository):
    def __init__(self, collection: AsyncIOMotorCollection) -> None:
        self._collection = collection

    async def get(self, correlation_id: UUID) -> CandidateCv | None:
        document = await self._collection.find_one(
            {"correlation_id": str(correlation_id), "status": AnalysisStatus.COMPLETED.value},
            sort=[("published_at", DESCENDING)],
        )
        if document is None:
            return None
        payload = {key: value for key, value in document.items() if key not in CV_METADATA_FIELDS}
        return CandidateCvMapper.to_domain(CVData.model_validate(payload))
