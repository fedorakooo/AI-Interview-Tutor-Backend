class ReportError(Exception):
    """Base exception for assessment report errors."""


class ReportNotReadyError(ReportError):
    """Raised when a report is requested before the interview session is completed."""


class FocusNotFoundError(ReportError):
    """Raised when the focus area does not exist in the interview template."""
