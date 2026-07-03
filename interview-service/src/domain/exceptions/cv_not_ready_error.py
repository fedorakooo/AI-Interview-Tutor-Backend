class CVNotReadyError(Exception):
    """Raised when no analyzed CV is available for interview in production."""

    def __init__(self, message: str = "Upload and wait for CV analysis before starting interview") -> None:
        super().__init__(message)
        self.message = message
