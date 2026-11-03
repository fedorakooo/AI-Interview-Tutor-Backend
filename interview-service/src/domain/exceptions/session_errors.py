from src.domain.exceptions.interview_service_error import InterviewServiceError


class SessionError(InterviewServiceError):
    """Base exception for interview session errors."""


class SessionCompletedError(SessionError):
    """Raised when a candidate answer arrives after the interview session is completed."""


class SessionBusyError(SessionError):
    """Raised when the exclusive turn lock of the session cannot be acquired in time."""


class NoPendingQuestionError(SessionError):
    """Raised when a candidate answer arrives while the interviewer has no open question."""


class EventSeqConflictError(SessionError):
    """Raised when an event with the same sequence number is already in the session journal."""


class InconsistentJournalError(SessionError):
    """Raised when the session journal violates an ordering, reference or quote rule."""


class EmptyInterviewerMessageError(SessionError):
    """Raised when the interviewer model returns no text and there is no fallback question."""
