from typing import Protocol

from shared_models.cv.cv_data import CVData
from shared_models.interview.report import InterviewReport


class InterviewContext(Protocol):
    """Read-only interview report context used for plan personalization."""

    session_id: str
    cv_correlation_id: str | None
    report: InterviewReport


class CVContext(Protocol):
    """Read-only CV analysis context used for plan personalization."""

    correlation_id: str | None
    cv_data: CVData


class ContextSnapshot(Protocol):
    """Combined CV and interview inputs available during plan generation."""

    cv_context: CVContext | None
    interview_context: InterviewContext | None


class IContextReader(Protocol):
    """Read-only port for CV and interview documents owned by other services."""

    async def get_latest_cv(self, user_id: str) -> CVContext | None:
        """Return the latest completed CV analysis for a user."""
        pass

    async def get_latest_interview(self, user_id: str) -> InterviewContext | None:
        """Return the latest completed interview report for a user."""
        pass

    async def get_interview_by_session(self, session_id: str) -> InterviewContext | None:
        """Return interview context for a specific session identifier."""
        pass
