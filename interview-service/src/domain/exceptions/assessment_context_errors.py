class AssessmentContextError(Exception):
    """Base exception for errors while loading an assessment attempt context."""


class AssessmentContextNotFoundError(AssessmentContextError):
    """Raised when the assessment attempt does not exist."""


class AssessmentNotReadyError(AssessmentContextError):
    """Raised when the assessment attempt cannot start yet, for example while a required CV is still analyzed."""


class AssessmentContextUnavailableError(AssessmentContextError):
    """Raised when the attempt context cannot be loaded from user management or is malformed."""
