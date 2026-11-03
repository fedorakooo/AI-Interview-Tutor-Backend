from uuid import UUID

from jwt_handler.exceptions import TokenError
from jwt_handler.interfaces import ICandidateInterviewTokenVerifier

from src.domain.exceptions.attempt_token_error import InvalidAttemptTokenError
from src.domain.interfaces.attempt_token_verifier import IAttemptTokenVerifier


class AttemptTokenVerifier(IAttemptTokenVerifier):
    def __init__(self, verifier: ICandidateInterviewTokenVerifier) -> None:
        self._verifier = verifier

    def verify(self, token: str) -> UUID:
        try:
            return UUID(self._verifier.verify(token)["sub"])
        except (TokenError, ValueError) as exc:
            raise InvalidAttemptTokenError() from exc
