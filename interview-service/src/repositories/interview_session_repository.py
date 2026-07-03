from datetime import UTC, datetime

from shared_models.interview.report import InterviewReport
from shared_models.interview.session import InterviewSessionDocument, InterviewSessionStatus
from src.domain.interfaces.mongo import IMongoRepository


class InterviewSessionRepository:
    def __init__(self, mongo_repository: IMongoRepository) -> None:
        self._mongo = mongo_repository

    async def create_session(
        self,
        session_id: str,
        user_id: str,
        *,
        cv_correlation_id: str | None,
        instance_id: str,
    ) -> InterviewSessionDocument:
        document = InterviewSessionDocument(
            session_id=session_id,
            user_id=user_id,
            status=InterviewSessionStatus.ACTIVE,
            started_at=datetime.now(UTC),
            overall_stage="Greeting",
            message_count=0,
            cv_correlation_id=cv_correlation_id,
            instance_id=instance_id,
        )
        await self._mongo.insert_one(document.to_mongo())
        return document

    async def update_session(
        self,
        session_id: str,
        *,
        status: InterviewSessionStatus | None = None,
        overall_stage: str | None = None,
        message_count: int | None = None,
        report: InterviewReport | None = None,
        completed_at: datetime | None = None,
    ) -> bool:
        update_data: dict = {}
        if status is not None:
            update_data["status"] = status.value
        if overall_stage is not None:
            update_data["overall_stage"] = overall_stage
        if message_count is not None:
            update_data["message_count"] = message_count
        if report is not None:
            update_data["report"] = report.model_dump(mode="json")
        if completed_at is not None:
            update_data["completed_at"] = completed_at.isoformat()
        if not update_data:
            return False
        return await self._mongo.update_one_by_field("session_id", session_id, update_data)

    async def get_session(self, session_id: str) -> InterviewSessionDocument | None:
        document = await self._mongo.find_one_by_field("session_id", session_id)
        if not document:
            return None
        return InterviewSessionDocument.from_mongo(document)

    async def list_user_sessions(
        self,
        user_id: str,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> list[InterviewSessionDocument]:
        documents = await self._mongo.find_many_by_field(
            "user_id",
            user_id,
            skip=skip,
            limit=limit,
        )
        return [InterviewSessionDocument.from_mongo(document) for document in documents]
