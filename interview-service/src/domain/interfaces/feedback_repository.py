from abc import ABC, abstractmethod
from uuid import UUID

from shared_models.assessment import FeedbackView


class IFeedbackRepository(ABC):
    """Persistence port for versioned candidate feedback texts."""

    @abstractmethod
    async def latest(self, attempt_id: UUID) -> FeedbackView | None:
        """Return the newest stored feedback version of an attempt."""

    @abstractmethod
    async def append(self, feedback: FeedbackView) -> bool:
        """Store a new feedback version and report false when that version already exists."""
