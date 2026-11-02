from abc import ABC, abstractmethod
from uuid import UUID

from shared_models.assessment import Assessment, ReviewEntry


class IAssessmentStore(ABC):
    @abstractmethod
    async def get(self, attempt_id: UUID) -> Assessment | None:
        """Return the stored report of an attempt without reviews."""

    @abstractmethod
    async def save(self, assessment: Assessment) -> None:
        """Store the generated report of an attempt, keeping the first one on a race."""

    @abstractmethod
    async def add_review(self, attempt_id: UUID, focus_id: str, entry: ReviewEntry) -> None:
        """Append a review entry to a focus area without changing earlier entries."""

    @abstractmethod
    async def list_reviews(self, attempt_id: UUID) -> dict[str, list[ReviewEntry]]:
        """Return the review entries of an attempt by focus area in creation order."""
