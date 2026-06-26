from abc import ABC, abstractmethod


class IPasswordHandler(ABC):
    """Interface for handling password operations."""

    @abstractmethod
    def hash_password(self, password: str) -> str:
        """Hash the given password using a secure algorithm."""
        pass

    @abstractmethod
    def validate_password(self, password: str, hashed_password: str) -> bool:
        """Validates if the given password matches the hashed password."""
        pass
