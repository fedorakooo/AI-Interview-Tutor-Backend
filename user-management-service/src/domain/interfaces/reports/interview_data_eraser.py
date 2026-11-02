from abc import ABC, abstractmethod
from uuid import UUID

from shared_models.assessment import ErasureResult


class IInterviewDataEraser(ABC):
    @abstractmethod
    async def erase(self, attempt_id: UUID, cv_correlation_id: UUID | None) -> ErasureResult:
        """Ask the interview service to delete every stored record of an attempt."""
