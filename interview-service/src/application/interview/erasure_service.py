from uuid import UUID

from shared_models.assessment import ErasureResult

from src.domain.interfaces.attempt_data_eraser import IAttemptDataEraser
from src.domain.interfaces.session_lock import ISessionLock


class AttemptErasureService:
    def __init__(self, lock: ISessionLock, eraser: IAttemptDataEraser) -> None:
        self._lock = lock
        self._eraser = eraser

    async def erase(self, attempt_id: UUID, cv_correlation_id: UUID | None) -> ErasureResult:
        async with self._lock.hold(str(attempt_id)):
            deleted = await self._eraser.erase(attempt_id, cv_correlation_id)
        return ErasureResult(attempt_id=attempt_id, deleted=deleted)
