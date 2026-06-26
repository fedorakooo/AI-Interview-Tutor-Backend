class NotSentError(Exception):
    """Custom exception for when an email fails to send after multiple attempts."""

    def __init__(self, recipient: str, attempts: int):
        self.recipient = recipient
        self.attempts = attempts
        message = f"Failed to send email to {recipient} after {attempts} attempts."
        super().__init__(message)
