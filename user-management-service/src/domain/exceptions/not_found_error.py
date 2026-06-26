class NotFoundError(Exception):
    """Exception occurs when a requested resource or item is not found."""

    def __init__(self, message: str = "Not found"):
        self.message = message
