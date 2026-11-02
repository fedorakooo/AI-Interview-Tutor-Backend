from uuid import UUID

from shared_models.assessment import AssessmentOverview, FocusDetail, ReviewRequest

from src.domain.interfaces.reports.interview_report_client import IInterviewReportClient
from src.infrastructure.interview_service.base_client import InterviewServiceClient


class InterviewServiceReportClient(InterviewServiceClient, IInterviewReportClient):
    async def get_overview(self, attempt_id: UUID) -> AssessmentOverview:
        return await self._request("GET", f"/api/internal/reports/{attempt_id}", AssessmentOverview)

    async def get_focus_detail(self, attempt_id: UUID, focus_id: str) -> FocusDetail:
        return await self._request("GET", f"/api/internal/reports/{attempt_id}/focus/{focus_id}", FocusDetail)

    async def add_review(self, attempt_id: UUID, focus_id: str, request: ReviewRequest) -> FocusDetail:
        return await self._request(
            "POST",
            f"/api/internal/reports/{attempt_id}/focus/{focus_id}/reviews",
            FocusDetail,
            body=request.model_dump(mode="json"),
        )
