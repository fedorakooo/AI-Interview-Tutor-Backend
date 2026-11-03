from abc import ABC, abstractmethod

from src.domain.interview.feedback import FeedbackDigest


class IFeedbackWriter(ABC):
    """LLM port for writing candidate feedback texts."""

    @abstractmethod
    async def write(self, digest: FeedbackDigest) -> str:
        """Write the candidate feedback text from the reduced digest."""
