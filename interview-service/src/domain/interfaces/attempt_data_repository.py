from abc import ABC, abstractmethod
from uuid import UUID


class IAttemptDataRepository(ABC):
    @abstractmethod
    async def erase(self, attempt_id: UUID, cv_correlation_id: UUID | None) -> dict[str, int]:
        """Delete every stored record of an attempt and return the deleted counts by kind."""
