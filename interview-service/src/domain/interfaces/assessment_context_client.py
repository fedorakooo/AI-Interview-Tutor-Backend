from abc import ABC, abstractmethod
from uuid import UUID

from shared_models.assessment import AssessmentContext


class IAssessmentContextClient(ABC):
    @abstractmethod
    async def get_context(self, attempt_id: UUID) -> AssessmentContext:
        """Fetch the trusted assessment context of one attempt."""
