from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jwt_handler.handlers import JWTTokenHandler

from src.api.dependencies.auth import get_token_handler
from src.api.dependencies.interview import get_interview_manager
from src.api.v1.endpoints.interview import CV_NOT_READY_CLOSE_CODE, get_cv_data_resolver, router
from src.domain.exceptions.cv_not_ready_error import CVNotReadyError


@pytest.fixture
def ws_app(token_handler: JWTTokenHandler, access_token: str, user_id: str) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    resolver = AsyncMock()
    resolver.resolve.side_effect = CVNotReadyError("Upload and wait for CV analysis")

    app.dependency_overrides[get_token_handler] = lambda: token_handler
    app.dependency_overrides[get_cv_data_resolver] = lambda: resolver
    app.dependency_overrides[get_interview_manager] = lambda: AsyncMock()
    return app


def test_websocket_sends_cv_not_ready_error(ws_app: FastAPI, access_token: str, user_id: str) -> None:
    client = TestClient(ws_app)

    with client.websocket_connect(
        f"/api/v1/interview/ws/{user_id}?token={access_token}",
    ) as websocket:
        payload = websocket.receive_json()
        assert payload["type"] == "error"
        assert payload["code"] == "CV_NOT_READY"
        assert "CV analysis" in payload["message"]

    assert CV_NOT_READY_CLOSE_CODE == 4001
