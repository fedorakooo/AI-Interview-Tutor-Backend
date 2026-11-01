from abc import ABC, abstractmethod
from typing import TypedDict


class CandidateAttemptTokenPayload(TypedDict):
    """Claims carried by a short-lived candidate assessment credential."""

    sub: str
    aud: str
    scope: str
    jti: str


class ICandidateAttemptTokenHandler(ABC):
    @abstractmethod
    def mint(self, attempt_id: str) -> str:
        """Create a token scoped to exactly one candidate attempt."""

    @abstractmethod
    def verify(self, token: str, expected_attempt_id: str) -> CandidateAttemptTokenPayload:
        """Verify audience, scope, expiry, and the attempt path binding."""
