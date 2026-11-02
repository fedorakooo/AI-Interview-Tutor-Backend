from abc import ABC, abstractmethod

from shared_models.assessment import SessionEvent


class IInterviewEventRepository(ABC):
    @abstractmethod
    async def append(self, event: SessionEvent) -> None:
        """Append an event to the session journal, rejecting a duplicate sequence number."""

    @abstractmethod
    async def list_events(self, session_id: str) -> list[SessionEvent]:
        """Return all events of a session ordered by sequence number."""
