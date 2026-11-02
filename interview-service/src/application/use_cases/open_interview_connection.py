from uuid import UUID

from jwt_handler.exceptions import TokenError
from jwt_handler.interfaces import ICandidateInterviewTokenVerifier

from src.domain.entities.interview_connection import InterviewConnection
from src.domain.exceptions.assessment_context_errors import AssessmentContextUnavailableError
from src.domain.exceptions.attempt_token_error import InvalidAttemptTokenError
from src.domain.interfaces.assessment_context_client import IAssessmentContextClient


class OpenInterviewConnectionUseCase:
    def __init__(
        self,
        token_verifier: ICandidateInterviewTokenVerifier,
        context_client: IAssessmentContextClient,
    ) -> None:
        self._token_verifier = token_verifier
        self._context_client = context_client

    async def __call__(self, token: str) -> InterviewConnection:
        attempt_id = self._attempt_id_from_token(token)
        context = await self._context_client.get_context(attempt_id)
        if context.attempt_id != attempt_id:
            raise AssessmentContextUnavailableError()
        return InterviewConnection(attempt_id=attempt_id, context=context)

    def _attempt_id_from_token(self, token: str) -> UUID:
        try:
            payload = self._token_verifier.verify(token)
            return UUID(payload["sub"])
        except (TokenError, ValueError) as exc:
            raise InvalidAttemptTokenError() from exc
