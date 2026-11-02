class InvalidAttemptTokenError(Exception):
    def __init__(self, message: str = "Invalid interview token") -> None:
        super().__init__(message)
