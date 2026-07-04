from dataclasses import dataclass, field
from unittest.mock import AsyncMock

import mongomock_motor
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from jwt_handler.handlers import JWTTokenHandler
from shared_models.practice.attempt import GradingResult
from src.agent.answer_grader import AnswerGrader
from src.api.dependencies.auth import get_token_handler
from src.api.v1.router import router
from src.app.container import build_container

from tests.conftest import PRIVATE_KEY, PUBLIC_KEY
from tests.fixtures.plan_fixtures import sample_plan_draft


@dataclass
class MockPublisher:
    published: list[tuple[str, str]] = field(default_factory=list)

    async def publish(self, queue_name: str, message: str) -> None:
        self.published.append((queue_name, message))


@pytest_asyncio.fixture
async def practice_test_env():
    mongo_client = mongomock_motor.AsyncMongoMockClient()
    mock_publisher = MockPublisher()
    mock_plan_generator = AsyncMock()
    mock_plan_generator.generate = AsyncMock(return_value=sample_plan_draft())
    test_answer_grader = AsyncMock()
    test_answer_grader.grade_mcq_single = AnswerGrader.grade_mcq_single
    test_answer_grader.grade_mcq_multi = AnswerGrader.grade_mcq_multi
    test_answer_grader.grade_flashcard = AnswerGrader.grade_flashcard
    test_answer_grader.find_exercise = AnswerGrader.find_exercise
    test_answer_grader.grade_open_question = AsyncMock(
        return_value=GradingResult(
            score=8.0,
            is_correct=True,
            feedback="Good answer",
            graded_by="llm",
        )
    )

    container, generate_plan_use_case, handle_interview_use_case, plan_repo, attempt_repo, profile_repo = (
        build_container(
            mongo_client,
            publisher=mock_publisher,
            plan_generator=mock_plan_generator,
            answer_grader=test_answer_grader,
        )
    )
    await plan_repo.ensure_indexes()
    await attempt_repo.ensure_indexes()
    await profile_repo.ensure_indexes()

    app = FastAPI()
    app.include_router(router)
    app.state.container = container
    app.state.mongo_client = mongo_client
    app.state.generate_plan_use_case = generate_plan_use_case
    app.state.handle_interview_use_case = handle_interview_use_case
    app.state.mock_publisher = mock_publisher
    app.state.mock_plan_generator = mock_plan_generator
    app.state.mock_answer_grader = test_answer_grader
    app.state.plan_repository = plan_repo
    app.state.profile_repository = profile_repo

    jwt_handler = JWTTokenHandler(public_key=PUBLIC_KEY, private_key=PRIVATE_KEY)
    app.dependency_overrides[get_token_handler] = lambda: jwt_handler

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield {
            "client": client,
            "container": container,
            "generate_plan_use_case": generate_plan_use_case,
            "handle_interview_use_case": handle_interview_use_case,
            "plan_repository": plan_repo,
            "profile_repository": profile_repo,
            "mock_publisher": mock_publisher,
            "mock_plan_generator": mock_plan_generator,
            "mock_answer_grader": test_answer_grader,
            "mongo_client": mongo_client,
        }
        mongo_client.close()
