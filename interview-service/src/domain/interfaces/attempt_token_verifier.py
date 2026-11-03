from abc import ABC, abstractmethod
from uuid import UUID


class IAttemptTokenVerifier(ABC):
    """Port for verifying the candidate interview token of an attempt."""

    @abstractmethod
    def verify(self, token: str) -> UUID:
        """Return the attempt id of a valid token or raise when the token is invalid."""
