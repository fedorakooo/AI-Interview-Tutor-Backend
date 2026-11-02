from abc import ABC, abstractmethod

from jwt_handler.value_objects import CandidateInterviewTokenPayload


class ICandidateInterviewTokenVerifier(ABC):
    @abstractmethod
    def verify(self, token: str | bytes) -> CandidateInterviewTokenPayload:
        """Verify a candidate interview token and return its claims."""
