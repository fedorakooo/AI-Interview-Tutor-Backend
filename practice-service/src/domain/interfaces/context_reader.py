from typing import Protocol

from shared_models.cv.cv_data import CVData
from shared_models.interview.report import InterviewReport


class InterviewContext(Protocol):
    session_id: str
    cv_correlation_id: str | None
    report: InterviewReport


class CVContext(Protocol):
    correlation_id: str | None
    cv_data: CVData


class ContextSnapshot(Protocol):
    cv_context: CVContext | None
    interview_context: InterviewContext | None


class IContextReader(Protocol):
    async def get_latest_cv(self, user_id: str) -> CVContext | None:
        pass

    async def get_latest_interview(self, user_id: str) -> InterviewContext | None:
        pass

    async def get_interview_by_session(self, session_id: str) -> InterviewContext | None:
        pass
