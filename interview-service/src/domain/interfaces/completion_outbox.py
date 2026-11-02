from abc import ABC, abstractmethod
from uuid import UUID

from shared_models.assessment import AssessmentCompleted


class ICompletionOutbox(ABC):
    @abstractmethod
    async def enqueue(self, event: AssessmentCompleted) -> None:
        """Store a completion event durably, ignoring a repeat of the same event."""

    @abstractmethod
    async def list_pending(self, limit: int) -> list[AssessmentCompleted]:
        """Return completion events that were not published yet, oldest first."""

    @abstractmethod
    async def mark_published(self, event_id: UUID) -> None:
        """Record that a completion event reached the broker."""
