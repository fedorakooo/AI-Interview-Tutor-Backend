from abc import ABC, abstractmethod
from uuid import UUID

from shared_models.assessment import ErasureResult


class IDataErasureService(ABC):
    """Use case of erasing the interview data of an attempt."""

    @abstractmethod
    async def erase(self, attempt_id: UUID, cv_correlation_id: UUID | None) -> ErasureResult:
        """Delete every stored record of an attempt and report the deleted counts."""
