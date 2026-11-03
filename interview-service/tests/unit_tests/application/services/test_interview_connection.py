from uuid import uuid4

import pytest
from jwt_handler.handlers import CandidateInterviewTokenVerifier
from jwt_handler.value_objects import TokenType, candidate_interview_scope
from src.domain.enums.cv_policy import CvPolicy
from src.domain.exceptions.assessment_context_errors import (
    AssessmentContextUnavailableError,
    AssessmentNotReadyError,
)
from src.domain.exceptions.attempt_token_error import InvalidAttemptTokenError

from tests.conftest import PUBLIC_KEY
from tests.fakes.builders import build_context
from tests.fakes.stack import FakeStack
from tests.fakes.tokens import mint_interview_token


def build_stack(error: Exception | None = None, policy: CvPolicy = CvPolicy.NONE) -> FakeStack:
    return FakeStack(
        context=build_context(policy),
        context_error=error,
        token_verifier=CandidateInterviewTokenVerifier(public_key=PUBLIC_KEY),
    )


async def test_attempt_id_comes_from_the_token() -> None:
    stack = build_stack()
    context = stack.context

    connection = await stack.container.interview_session_service.open_connection(
        mint_interview_token(context.attempt_id)
    )

    assert connection.attempt_id == context.attempt_id
    assert connection.context == context
    assert stack.context_client.requested == [context.attempt_id]


@pytest.mark.parametrize("token", ["not-a-jwt", ""])
async def test_garbage_token_is_rejected_without_calling_user_management(token: str) -> None:
    stack = build_stack()

    with pytest.raises(InvalidAttemptTokenError):
        await stack.container.interview_session_service.open_connection(token)

    assert stack.context_client.requested == []


async def test_token_of_another_type_is_rejected() -> None:
    stack = build_stack()
    token = mint_interview_token(stack.context.attempt_id, type=TokenType.ACCESS)

    with pytest.raises(InvalidAttemptTokenError):
        await stack.container.interview_session_service.open_connection(token)


async def test_non_uuid_subject_is_rejected() -> None:
    stack = build_stack()
    token = mint_interview_token(uuid4(), sub="attempt-1", scope=candidate_interview_scope("attempt-1"))

    with pytest.raises(InvalidAttemptTokenError):
        await stack.container.interview_session_service.open_connection(token)


async def test_context_for_another_attempt_is_rejected() -> None:
    stack = build_stack()

    with pytest.raises(AssessmentContextUnavailableError):
        await stack.container.interview_session_service.open_connection(mint_interview_token(uuid4()))


async def test_context_errors_propagate() -> None:
    stack = build_stack(AssessmentNotReadyError())

    with pytest.raises(AssessmentNotReadyError):
        await stack.container.interview_session_service.open_connection(mint_interview_token(stack.context.attempt_id))
