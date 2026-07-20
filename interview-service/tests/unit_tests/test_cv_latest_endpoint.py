from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jwt_handler.handlers import JWTTokenHandler
from shared_models.messaging.common import AnalysisStatus
from src.agent.data.sample_data import SAMPLE_CV
from src.api.dependencies.auth import get_token_handler
from src.api.dependencies.mongo import get_cv_analysis_repository
from src.api.v1.endpoints.cv import router


@pytest.fixture
def cv_app(token_handler: JWTTokenHandler) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_token_handler] = lambda: token_handler
    return app


def test_get_latest_cv_returns_parsed_cv(cv_app: FastAPI, access_token: str, user_id: str) -> None:
    mongo_repository = AsyncMock()
    mongo_repository.find_latest_by_field.return_value = {
        "correlation_id": "corr-42",
        "user_id": user_id,
        "status": AnalysisStatus.COMPLETED.value,
        "user_name": "Jane Doe",
        "specialization": "Backend Developer",
    }
    cv_app.dependency_overrides[get_cv_analysis_repository] = lambda: mongo_repository

    client = TestClient(cv_app)
    response = client.get(
        "/api/v1/interview/cv/latest",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["correlation_id"] == "corr-42"
    assert body["source"] == "mongodb"
    assert body["cv"]["user_name"] == "Jane Doe"
    mongo_repository.find_latest_by_field.assert_awaited_once()


def test_get_latest_cv_returns_404_when_missing(cv_app: FastAPI, access_token: str) -> None:
    mongo_repository = AsyncMock()
    mongo_repository.find_latest_by_field.return_value = None
    cv_app.dependency_overrides[get_cv_analysis_repository] = lambda: mongo_repository

    client = TestClient(cv_app)
    response = client.get(
        "/api/v1/interview/cv/latest",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 404
    assert "No completed CV" in response.json()["detail"]


def test_get_latest_cv_never_returns_sample_fallback(cv_app: FastAPI, access_token: str, monkeypatch) -> None:
    from src.config import settings

    monkeypatch.setattr(settings, "allow_sample_cv_fallback", True)
    mongo_repository = AsyncMock()
    mongo_repository.find_latest_by_field.return_value = None
    cv_app.dependency_overrides[get_cv_analysis_repository] = lambda: mongo_repository

    client = TestClient(cv_app)
    response = client.get(
        "/api/v1/interview/cv/latest",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 404
    assert SAMPLE_CV.user_name not in response.text
