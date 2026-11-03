from abc import ABC, abstractmethod
from uuid import UUID

from shared_models.assessment import FeedbackView


class ICandidateFeedbackService(ABC):
    """Use cases of the candidate feedback text."""

    @abstractmethod
    async def get(self, attempt_id: UUID) -> FeedbackView:
        """Return the latest feedback text and generate it on the first request."""

    @abstractmethod
    async def edit(self, attempt_id: UUID, editor_id: UUID, text: str) -> FeedbackView:
        """Store an edited feedback text as a new version."""
