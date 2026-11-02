from abc import ABC, abstractmethod
from uuid import UUID

from shared_models.assessment import AssessmentOverview, FocusDetail, ReviewRequest


class IInterviewReportClient(ABC):
    @abstractmethod
    async def get_overview(self, attempt_id: UUID) -> AssessmentOverview:
        """Fetch the report overview of an attempt from the interview service."""

    @abstractmethod
    async def get_focus_detail(self, attempt_id: UUID, focus_id: str) -> FocusDetail:
        """Fetch the detailed view of one report focus area."""

    @abstractmethod
    async def add_review(self, attempt_id: UUID, focus_id: str, request: ReviewRequest) -> FocusDetail:
        """Append a reviewer entry to one report focus area."""
