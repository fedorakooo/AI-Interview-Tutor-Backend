from dataclasses import dataclass
from typing import Any

from shared_models.cv.cv_data import CVData
from shared_models.interview.report import InterviewReport
from shared_models.interview.session import InterviewSessionDocument, InterviewSessionStatus
from shared_models.messaging.common import AnalysisStatus
from src.config import settings
from src.infrastructure.mongo.client import MongoClientFactory

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


@dataclass
class CVContextData:
    correlation_id: str | None
    cv_data: CVData


@dataclass
class InterviewContextData:
    session_id: str
    cv_correlation_id: str | None
    report: InterviewReport


class ContextReader:
    def __init__(self, mongo_client) -> None:
        self._client = mongo_client
        self._cv_collection = MongoClientFactory.get_collection(
            mongo_client,
            settings.mongo_settings.db_name,
            settings.mongo_settings.cv_analysis_collection_name,
        )
        self._sessions_collection = MongoClientFactory.get_collection(
            mongo_client,
            settings.mongo_settings.db_name,
            settings.mongo_settings.interview_sessions_collection_name,
        )

    async def get_latest_cv(self, user_id: str) -> CVContextData | None:
        document = await self._cv_collection.find_one(
            {
                settings.mongo_settings.cv_user_id_field: user_id,
                "status": AnalysisStatus.COMPLETED.value,
            },
            sort=[("published_at", -1)],
        )
        if not document:
            return None
        cv_payload = {key: value for key, value in document.items() if key not in CV_METADATA_FIELDS}
        correlation_id = document.get("correlation_id")
        return CVContextData(
            correlation_id=str(correlation_id) if correlation_id is not None else None,
            cv_data=CVData.model_validate(self._normalize_cv_payload(cv_payload)),
        )

    async def get_latest_interview(self, user_id: str) -> InterviewContextData | None:
        document = await self._sessions_collection.find_one(
            {
                "user_id": user_id,
                "status": InterviewSessionStatus.COMPLETED.value,
                "report": {"$ne": None},
            },
            sort=[("completed_at", -1)],
        )
        if not document:
            return None
        return self._to_interview_context(document)

    async def get_interview_by_session(self, session_id: str) -> InterviewContextData | None:
        document = await self._sessions_collection.find_one({"session_id": session_id})
        if not document or document.get("report") is None:
            return None
        return self._to_interview_context(document)

    @staticmethod
    def _to_interview_context(document: dict[str, Any]) -> InterviewContextData:
        session = InterviewSessionDocument.from_mongo(document)
        if session.report is None:
            raise ValueError("Interview session has no report")
        return InterviewContextData(
            session_id=session.session_id,
            cv_correlation_id=session.cv_correlation_id,
            report=session.report,
        )

    @staticmethod
    def _normalize_cv_payload(payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        skills = normalized.get("skills")
        if skills and isinstance(skills[0], str):
            normalized["skills"] = [{"name": skill} for skill in skills]
        return normalized
