from abc import ABC, abstractmethod

from shared_models.assessment import AssessmentCompleted


class IAssessmentCompletedPublisher(ABC):
    """Outbound messaging port for publishing assessment completion events."""

    @abstractmethod
    async def publish(self, event: AssessmentCompleted) -> None:
        """Publish the completion notification of a finished assessment."""
