from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.value_objects.candidate_cv import CandidateCv


class ICandidateCvRepository(ABC):
    """Read-only port for the analyzed CV documents owned by the analyze service."""

    @abstractmethod
    async def get(self, correlation_id: UUID) -> CandidateCv | None:
        """Return the analyzed CV of an attempt, or nothing when it is not available."""
