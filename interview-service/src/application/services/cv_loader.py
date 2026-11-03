from uuid import UUID

from src.domain.entities.interview_connection import InterviewConnection
from src.domain.enums.cv_policy import CvPolicy
from src.domain.exceptions.assessment_context_errors import AssessmentNotReadyError
from src.domain.interfaces.repositories.candidate_cv_repository import ICandidateCvRepository
from src.domain.value_objects.candidate_cv import CandidateCv

CV_CACHE_SIZE = 256


class CvLoader:
    def __init__(self, cv_repository: ICandidateCvRepository) -> None:
        self._cv_repository = cv_repository
        self._cache: dict[UUID, CandidateCv] = {}

    async def load(self, connection: InterviewConnection) -> CandidateCv | None:
        context = connection.context
        if context.cv_correlation_id is None:
            return None
        cached = self._cache.get(context.cv_correlation_id)
        if cached is not None:
            return cached
        cv = await self._cv_repository.get(context.cv_correlation_id)
        if cv is None and context.cv_policy == CvPolicy.REQUIRED:
            raise AssessmentNotReadyError()
        if cv is not None:
            if len(self._cache) >= CV_CACHE_SIZE:
                self._cache.clear()
            self._cache[context.cv_correlation_id] = cv
        return cv
