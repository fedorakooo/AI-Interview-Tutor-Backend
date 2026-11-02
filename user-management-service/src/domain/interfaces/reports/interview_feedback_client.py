from abc import ABC, abstractmethod
from uuid import UUID

from shared_models.assessment import FeedbackEditRequest, FeedbackView


class IInterviewFeedbackClient(ABC):
    @abstractmethod
    async def get_feedback(self, attempt_id: UUID) -> FeedbackView:
        """Fetch the current candidate feedback text from the interview service."""

    @abstractmethod
    async def edit_feedback(self, attempt_id: UUID, request: FeedbackEditRequest) -> FeedbackView:
        """Store a recruiter edited feedback text as a new version."""
