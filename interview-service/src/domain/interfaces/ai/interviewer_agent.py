from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from src.domain.value_objects.interviewer_request import InterviewerRequest


class IInterviewerAgent(ABC):
    """LLM port for streaming interviewer messages."""

    @abstractmethod
    def stream_message(self, request: InterviewerRequest) -> AsyncIterator[str]:
        """Stream the next interviewer message as text deltas."""
