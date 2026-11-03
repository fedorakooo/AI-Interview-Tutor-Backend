from uuid import UUID

from shared_models.assessment import ErasureResult

from src.application.interfaces.data_erasure_service import IDataErasureService
from src.domain.interfaces.repositories.attempt_data_repository import IAttemptDataRepository
from src.domain.interfaces.session.session_lock import ISessionLock


class DataErasureService(IDataErasureService):
    def __init__(self, lock: ISessionLock, attempt_data_repository: IAttemptDataRepository) -> None:
        self._lock = lock
        self._attempt_data_repository = attempt_data_repository

    async def erase(self, attempt_id: UUID, cv_correlation_id: UUID | None) -> ErasureResult:
        async with self._lock.hold(str(attempt_id)):
            deleted = await self._attempt_data_repository.erase(attempt_id, cv_correlation_id)
        return ErasureResult(attempt_id=attempt_id, deleted=deleted)
