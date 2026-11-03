from uuid import UUID

from src.domain.entities.interview_connection import InterviewConnection
from src.domain.exceptions.assessment_context_errors import AssessmentContextUnavailableError
from src.domain.interfaces.assessment_context_client import IAssessmentContextClient
from src.domain.interfaces.attempt_token_verifier import IAttemptTokenVerifier


class OpenInterviewConnectionUseCase:
    def __init__(
        self,
        token_verifier: IAttemptTokenVerifier,
        context_client: IAssessmentContextClient,
    ) -> None:
        self._token_verifier = token_verifier
        self._context_client = context_client

    async def __call__(self, token: str) -> InterviewConnection:
        attempt_id = self._token_verifier.verify(token)
        context = await self._context_client.get_context(attempt_id)
        if context.attempt_id != attempt_id:
            raise AssessmentContextUnavailableError()
        return InterviewConnection(attempt_id=attempt_id, context=context)
