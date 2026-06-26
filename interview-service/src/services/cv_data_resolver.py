from typing import Any

from src.agent.data.sample_data import SAMPLE_CV
from src.config import settings
from src.domain.interfaces.mongo import IMongoRepository
from src.domain.models.cv_data import CVData
from src.logger import app_logger

CV_METADATA_FIELDS = {"_id", "user_id", "source_url", "published_at"}


class CVDataResolver:
    """Resolves CV context for interviews from analyze-service MongoDB documents."""

    def __init__(self, mongo_repository: IMongoRepository):
        self.mongo_repository = mongo_repository

    async def resolve(self, user_id: str) -> CVData:
        document = await self.mongo_repository.find_latest_by_field(
            settings.mongo_settings.cv_user_id_field,
            user_id,
        )
        if document is None:
            app_logger.info("No analyzed CV found for user %s, using sample profile", user_id)
            return SAMPLE_CV

        cv_payload = {key: value for key, value in document.items() if key not in CV_METADATA_FIELDS}
        return CVData(**self._normalize_cv_payload(cv_payload))

    @staticmethod
    def _normalize_cv_payload(payload: dict[str, Any]) -> dict[str, Any]:
        languages = payload.get("languages")
        if languages:
            payload["languages"] = [
                {
                    **language,
                    "proficiency": language.get("proficiency"),
                }
                for language in languages
            ]
        return payload
