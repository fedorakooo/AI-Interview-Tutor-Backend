from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import WebSocket
from shared_models.cv.cv_data import CVData
from shared_models.interview.session import InterviewSessionStatus

from src.api.v1.managers.interview_manager import (
    SERVER_SHUTDOWN_CLOSE_CODE,
    ActiveSession,
    InterviewConnectionManager,
)
from src.domain.models.user_profile import UserProfile


@pytest.fixture
def interview_manager() -> InterviewConnectionManager:
    return InterviewConnectionManager(
        interview_workflow=AsyncMock(),
        session_registry=AsyncMock(),
        session_repository=AsyncMock(),
        instance_id="test-instance",
    )


@pytest.fixture
def websocket() -> AsyncMock:
    ws = AsyncMock(spec=WebSocket)
    ws.close = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


@pytest.mark.asyncio
async def test_rejects_new_connections_during_shutdown(
    interview_manager: InterviewConnectionManager,
    websocket: AsyncMock,
) -> None:
    interview_manager._accepting_connections = False
    user = UserProfile(id=uuid4())

    with pytest.raises(RuntimeError, match="Service is shutting down"):
        await interview_manager.start_interview(
            websocket,
            user,
            CVData(user_name="Jane Doe"),
        )

    websocket.close.assert_awaited_once_with(code=SERVER_SHUTDOWN_CLOSE_CODE)
    websocket.accept.assert_not_awaited()


@pytest.mark.asyncio
async def test_shutdown_suspends_active_sessions(interview_manager: InterviewConnectionManager) -> None:
    session_id = str(uuid4())
    user_id = str(uuid4())
    websocket = AsyncMock(spec=WebSocket)
    websocket.close = AsyncMock()
    websocket.send_text = AsyncMock()

    interview_manager._active_sessions[session_id] = ActiveSession(
        session_id=session_id,
        user_id=user_id,
        websocket=websocket,
        started_at=datetime.now(UTC),
    )

    snapshot = MagicMock()
    snapshot.values = {"overall_stage": "GREETING", "messages": ["hello"]}
    interview_manager.interview_workflow.aget_state.return_value = snapshot

    await interview_manager.shutdown()

    interview_manager.session_repository.update_session.assert_awaited_once()
    update_kwargs = interview_manager.session_repository.update_session.await_args.kwargs
    assert update_kwargs["status"] == InterviewSessionStatus.SUSPENDED
    interview_manager.session_registry.unregister_session.assert_awaited_once_with(session_id, user_id)
    websocket.close.assert_awaited_once_with(code=SERVER_SHUTDOWN_CLOSE_CODE)
    assert session_id not in interview_manager._active_sessions
    assert interview_manager.accepting_connections is False
