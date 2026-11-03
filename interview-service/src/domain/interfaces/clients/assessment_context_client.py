from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.value_objects.assessment_context import AssessmentContext


class IAssessmentContextClient(ABC):
    """Port for reading the trusted assessment context owned by user management."""

    @abstractmethod
    async def get_context(self, attempt_id: UUID) -> AssessmentContext:
        """Fetch the trusted assessment context of one attempt."""
