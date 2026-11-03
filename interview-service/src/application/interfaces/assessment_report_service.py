from abc import ABC, abstractmethod
from uuid import UUID

from shared_models.assessment import AssessmentOverview, FocusDetail, ReviewRequest


class IAssessmentReportService(ABC):
    """Use cases of the assessment report and its reviews."""

    @abstractmethod
    async def get_overview(self, attempt_id: UUID) -> AssessmentOverview:
        """Return the report overview of a completed attempt."""

    @abstractmethod
    async def get_focus_detail(self, attempt_id: UUID, focus_id: str) -> FocusDetail:
        """Return the evidence timeline of one focus area."""

    @abstractmethod
    async def add_review(self, attempt_id: UUID, focus_id: str, request: ReviewRequest) -> FocusDetail:
        """Append a reviewer note to a focus area and return the updated detail."""
