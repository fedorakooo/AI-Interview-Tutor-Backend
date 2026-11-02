from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from src.domain.interview.dto import InterviewerRequest


class IInterviewerAgent(ABC):
    @abstractmethod
    def stream_message(self, request: InterviewerRequest) -> AsyncIterator[str]:
        """Stream the next interviewer message as text deltas."""
