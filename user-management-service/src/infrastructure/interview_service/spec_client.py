from shared_models.assessment import AssessmentTemplateSnapshot, TemplateDraftRequest

from src.domain.interfaces.reports.interview_spec_client import IInterviewSpecClient
from src.infrastructure.interview_service.base_client import InterviewServiceClient


class InterviewServiceSpecClient(InterviewServiceClient, IInterviewSpecClient):
    async def create_template_draft(self, request: TemplateDraftRequest) -> AssessmentTemplateSnapshot:
        return await self._request(
            "POST", "/api/internal/spec-drafts", AssessmentTemplateSnapshot, body=request.model_dump(mode="json")
        )
