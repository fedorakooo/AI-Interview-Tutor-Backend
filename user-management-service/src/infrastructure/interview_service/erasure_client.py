from uuid import UUID

from shared_models.assessment import ErasureRequest, ErasureResult

from src.domain.interfaces.reports.interview_data_eraser import IInterviewDataEraser
from src.infrastructure.interview_service.base_client import InterviewServiceClient


class InterviewServiceErasureClient(InterviewServiceClient, IInterviewDataEraser):
    async def erase(self, attempt_id: UUID, cv_correlation_id: UUID | None) -> ErasureResult:
        return await self._request(
            "POST",
            f"/api/internal/erasure/{attempt_id}",
            ErasureResult,
            body=ErasureRequest(cv_correlation_id=cv_correlation_id).model_dump(mode="json"),
        )
