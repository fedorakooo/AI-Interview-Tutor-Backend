from uuid import UUID

from shared_models.cv.cv_data import CVData
from shared_models.messaging.common import AnalysisStatus

from src.domain.interfaces.candidate_cv_repository import ICandidateCvRepository
from src.domain.interfaces.mongo import IMongoRepository

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
    def __init__(self, repository: IMongoRepository) -> None:
        self._repository = repository

    async def get(self, correlation_id: UUID) -> CVData | None:
        document = await self._repository.find_latest_by_field(
            "correlation_id",
            str(correlation_id),
            extra_filter={"status": AnalysisStatus.COMPLETED.value},
        )
        if document is None:
            return None
        payload = {key: value for key, value in document.items() if key not in CV_METADATA_FIELDS}
        return CVData.model_validate(payload)
