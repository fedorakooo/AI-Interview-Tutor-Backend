class UserBlockedError(Exception):
    """Exception raised when a user is blocked and cannot perform the action."""

    def __init__(self, username: str):
        super().__init__(f"User with username [{username}] is blocked")


class UserDeletionConflictError(Exception):
    def __init__(self):
        super().__init__("Account is referenced by retained records; resolve ownership and retention before deletion")
