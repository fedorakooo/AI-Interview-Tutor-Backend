from uuid import UUID

from shared_models.assessment import AssessmentTemplateSnapshot

from src.domain.interfaces.assessment_context_client import IAssessmentContextClient


class GetAssessmentTemplateUseCase:
    def __init__(self, context_client: IAssessmentContextClient):
        self._context_client = context_client

    async def __call__(self, attempt_id: UUID) -> AssessmentTemplateSnapshot:
        return (await self._context_client.get_context(attempt_id)).template
