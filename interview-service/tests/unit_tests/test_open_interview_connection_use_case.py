from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
import pytest
from jwt_handler.handlers import CandidateInterviewTokenVerifier
from jwt_handler.value_objects import CANDIDATE_INTERVIEW_AUDIENCE, TokenType, candidate_interview_scope
from shared_models.assessment import AssessmentContext, CvPolicy
from shared_models.assessment.mocks import mock_assessment_context
from src.application.use_cases.open_interview_connection import OpenInterviewConnectionUseCase
from src.domain.exceptions.assessment_context_errors import (
    AssessmentContextUnavailableError,
    AssessmentNotReadyError,
)
from src.domain.exceptions.attempt_token_error import InvalidAttemptTokenError
from src.domain.interfaces.assessment_context_client import IAssessmentContextClient
from src.infrastructure.jwt.attempt_token_verifier import AttemptTokenVerifier

from tests.conftest import PRIVATE_KEY, PUBLIC_KEY


class FakeContextClient(IAssessmentContextClient):
    def __init__(self, context: AssessmentContext | None = None, error: Exception | None = None) -> None:
        self.context = context
        self.error = error
        self.requested: list[UUID] = []

    async def get_context(self, attempt_id: UUID) -> AssessmentContext:
        self.requested.append(attempt_id)
        if self.error is not None:
            raise self.error
        assert self.context is not None
        return self.context


def mint_interview_token(attempt_id: UUID, **overrides: object) -> str:
    now = datetime.now(UTC)
    claims: dict[str, object] = {
        "sub": str(attempt_id),
        "aud": CANDIDATE_INTERVIEW_AUDIENCE,
        "scope": candidate_interview_scope(str(attempt_id)),
        "jti": uuid4().hex,
        "type": TokenType.CANDIDATE_INTERVIEW,
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    claims.update(overrides)
    return jwt.encode(claims, PRIVATE_KEY, algorithm="RS256")


def build_use_case(client: FakeContextClient) -> OpenInterviewConnectionUseCase:
    return OpenInterviewConnectionUseCase(
        AttemptTokenVerifier(CandidateInterviewTokenVerifier(public_key=PUBLIC_KEY)), client
    )


async def test_attempt_id_comes_from_the_token() -> None:
    context = mock_assessment_context(CvPolicy.NONE)
    client = FakeContextClient(context)

    connection = await build_use_case(client)(mint_interview_token(context.attempt_id))

    assert connection.attempt_id == context.attempt_id
    assert connection.context == context
    assert client.requested == [context.attempt_id]


@pytest.mark.parametrize("token", ["not-a-jwt", ""])
async def test_garbage_token_is_rejected_without_calling_user_management(token: str) -> None:
    client = FakeContextClient(mock_assessment_context())

    with pytest.raises(InvalidAttemptTokenError):
        await build_use_case(client)(token)

    assert client.requested == []


async def test_token_of_another_type_is_rejected() -> None:
    context = mock_assessment_context()
    client = FakeContextClient(context)
    token = mint_interview_token(context.attempt_id, type=TokenType.ACCESS)

    with pytest.raises(InvalidAttemptTokenError):
        await build_use_case(client)(token)


async def test_non_uuid_subject_is_rejected() -> None:
    client = FakeContextClient(mock_assessment_context())
    token = mint_interview_token(uuid4(), sub="attempt-1", scope=candidate_interview_scope("attempt-1"))

    with pytest.raises(InvalidAttemptTokenError):
        await build_use_case(client)(token)


async def test_context_for_another_attempt_is_rejected() -> None:
    client = FakeContextClient(mock_assessment_context())

    with pytest.raises(AssessmentContextUnavailableError):
        await build_use_case(client)(mint_interview_token(uuid4()))


async def test_context_errors_propagate() -> None:
    attempt_id = uuid4()
    client = FakeContextClient(error=AssessmentNotReadyError())

    with pytest.raises(AssessmentNotReadyError):
        await build_use_case(client)(mint_interview_token(attempt_id))
