from abc import ABC, abstractmethod


class IAccessTokenGenerator(ABC):
    """Abstract class for generating an access tokens."""

    @abstractmethod
    def generate_access_token(
        self, user_id: str, username: str, user_role: str, is_blocked: bool, auth_version: int = 0
    ) -> str:
        """Generate a new access token."""
        pass
