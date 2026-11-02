from abc import ABC, abstractmethod
from uuid import UUID

from shared_models.cv.cv_data import CVData


class ICandidateCvRepository(ABC):
    @abstractmethod
    async def get(self, correlation_id: UUID) -> CVData | None:
        """Return the analyzed CV of an attempt, or nothing when it is not available."""
