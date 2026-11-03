class InvalidAttemptTokenError(Exception):
    """Raised when the candidate interview token is invalid, expired or has no valid attempt id."""

    def __init__(self, message: str = "Invalid interview token") -> None:
        super().__init__(message)
