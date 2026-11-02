from uuid import UUID

from shared_models.assessment import ErasureResult

from src.domain.interfaces.attempt_data_repository import IAttemptDataRepository
from src.domain.interfaces.session_lock import ISessionLock


class EraseAttemptDataUseCase:
    def __init__(self, lock: ISessionLock, attempt_data_repository: IAttemptDataRepository):
        self._lock = lock
        self._attempt_data_repository = attempt_data_repository

    async def __call__(self, attempt_id: UUID, cv_correlation_id: UUID | None) -> ErasureResult:
        async with self._lock.hold(str(attempt_id)):
            deleted = await self._attempt_data_repository.erase(attempt_id, cv_correlation_id)
        return ErasureResult(attempt_id=attempt_id, deleted=deleted)
