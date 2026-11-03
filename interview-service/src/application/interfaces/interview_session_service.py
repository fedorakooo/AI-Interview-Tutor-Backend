from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from uuid import UUID

from src.application.dtos.session_finished import SessionFinished
from src.application.dtos.session_output import SessionOutput
from src.application.dtos.transcript_entry import TranscriptEntry
from src.domain.entities.interview_connection import InterviewConnection


class IInterviewSessionService(ABC):
    """Use cases of one live candidate interview session."""

    @abstractmethod
    async def open_connection(self, token: str) -> InterviewConnection:
        """Verify the candidate token and load the attempt context into a connection."""

    @abstractmethod
    async def register_connection(self, connection: InterviewConnection) -> str:
        """Register the connection as the latest live one and return its presence token."""

    @abstractmethod
    async def transcript(
        self, connection: InterviewConnection, last_event_id: UUID | None
    ) -> list[TranscriptEntry | SessionFinished]:
        """Return the visible transcript entries that follow the last event the client already has."""

    @abstractmethod
    def open_session(self, connection: InterviewConnection) -> AsyncIterator[SessionOutput]:
        """Start or resume the session and stream the next interviewer output."""

    @abstractmethod
    def answer(self, connection: InterviewConnection, turn_id: UUID, text: str) -> AsyncIterator[SessionOutput]:
        """Record a candidate answer and stream the interviewer reply."""

    @abstractmethod
    async def pause(self, connection: InterviewConnection, token: str) -> None:
        """Pause the session when the connection with this presence token was the latest one."""
