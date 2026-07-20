from typing import Any, Literal

from pydantic import BaseModel
from shared_models.cv.cv_data import CVData
from shared_models.messaging.common import AnalysisStatus

from src.agent.data.sample_data import SAMPLE_CV
from src.config import settings
from src.domain.exceptions.cv_not_ready_error import CVNotReadyError
from src.domain.interfaces.mongo import IMongoRepository
from src.logger import app_logger

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


class CVResolutionResult(BaseModel):
    cv_data: CVData
    source: Literal["mongodb", "sample_fallback"]
    correlation_id: str | None = None


class CVDataResolver:
    """Resolves CV context for interviews from analyze-service MongoDB documents."""

    def __init__(self, mongo_repository: IMongoRepository):
        self.mongo_repository = mongo_repository

    async def resolve(self, user_id: str, *, allow_sample_fallback: bool | None = None) -> CVResolutionResult:
        document = await self.mongo_repository.find_latest_by_field(
            settings.mongo_settings.cv_user_id_field,
            user_id,
            extra_filter={"status": AnalysisStatus.COMPLETED.value},
        )
        if document is None:
            use_sample = (
                settings.allow_sample_cv_fallback if allow_sample_fallback is None else allow_sample_fallback
            )
            if not use_sample:
                raise CVNotReadyError()

            app_logger.warning("No analyzed CV found for user %s, using sample profile", user_id)
            return CVResolutionResult(cv_data=SAMPLE_CV, source="sample_fallback")

        cv_payload = {key: value for key, value in document.items() if key not in CV_METADATA_FIELDS}
        correlation_id = document.get("correlation_id")
        return CVResolutionResult(
            cv_data=CVData.model_validate(self._normalize_cv_payload(cv_payload)),
            source="mongodb",
            correlation_id=str(correlation_id) if correlation_id is not None else None,
        )

    async def get_latest_completed(self, user_id: str) -> CVResolutionResult:
        """Return the latest completed CV without sample fallback (for REST clients)."""
        return await self.resolve(user_id, allow_sample_fallback=False)

    @staticmethod
    def _normalize_cv_payload(payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)

        languages = normalized.get("languages")
        if languages:
            normalized["languages"] = [
                {
                    **language,
                    "proficiency": language.get("proficiency"),
                }
                for language in languages
            ]

        return normalized
