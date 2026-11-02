from uuid import UUID

from shared_models.assessment import FeedbackEditRequest, FeedbackView

from src.domain.interfaces.reports.interview_feedback_client import IInterviewFeedbackClient
from src.infrastructure.interview_service.base_client import InterviewServiceClient


class InterviewServiceFeedbackClient(InterviewServiceClient, IInterviewFeedbackClient):
    async def get_feedback(self, attempt_id: UUID) -> FeedbackView:
        return await self._request("GET", f"/api/internal/feedback/{attempt_id}", FeedbackView)

    async def edit_feedback(self, attempt_id: UUID, request: FeedbackEditRequest) -> FeedbackView:
        return await self._request(
            "PUT", f"/api/internal/feedback/{attempt_id}", FeedbackView, body=request.model_dump(mode="json")
        )
