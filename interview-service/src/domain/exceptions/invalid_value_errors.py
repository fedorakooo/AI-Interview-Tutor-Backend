from src.domain.exceptions.interview_service_error import InterviewServiceError


class InvalidDomainValueError(InterviewServiceError):
    """Raised when a domain object is built from values that break its invariants."""
