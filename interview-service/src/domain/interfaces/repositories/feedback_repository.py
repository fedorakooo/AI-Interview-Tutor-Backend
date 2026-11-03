from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.feedback_entry import FeedbackEntry


class IFeedbackRepository(ABC):
    """Persistence port for versioned candidate feedback texts."""

    @abstractmethod
    async def latest(self, attempt_id: UUID) -> FeedbackEntry | None:
        """Return the newest stored feedback version of an attempt."""

    @abstractmethod
    async def append(self, feedback: FeedbackEntry) -> bool:
        """Store a new feedback version and report false when that version already exists."""
