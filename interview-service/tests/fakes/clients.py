from uuid import UUID

from src.domain.interfaces.clients.assessment_context_client import IAssessmentContextClient
from src.domain.value_objects.assessment_context import AssessmentContext


class FakeContextClient(IAssessmentContextClient):
    def __init__(self, context: AssessmentContext, error: Exception | None = None) -> None:
        self.context = context
        self.error = error
        self.requested: list[UUID] = []

    async def get_context(self, attempt_id: UUID) -> AssessmentContext:
        self.requested.append(attempt_id)
        if self.error is not None:
            raise self.error
        return self.context
