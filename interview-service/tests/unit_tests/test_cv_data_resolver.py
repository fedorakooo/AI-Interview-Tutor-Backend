from unittest.mock import AsyncMock

import pytest
from shared_models.messaging.common import AnalysisStatus
from src.agent.data.sample_data import SAMPLE_CV
from src.config import settings
from src.services.cv_data_resolver import CVDataResolver


@pytest.mark.asyncio
async def test_resolver_returns_mongodb_cv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "environment", "development")
    mongo_repository = AsyncMock()
    mongo_repository.find_latest_by_field.return_value = {
        "correlation_id": "corr-1",
        "user_id": "user-1",
        "status": AnalysisStatus.COMPLETED.value,
        "published_at": "2026-07-03T10:00:00+00:00",
        "user_name": "Jane Doe",
        "specialization": "Backend Developer",
    }

    result = await CVDataResolver(mongo_repository).resolve("user-1")

    assert result.source == "mongodb"
    assert result.correlation_id == "corr-1"
    assert result.cv_data.user_name == "Jane Doe"


@pytest.mark.asyncio
async def test_resolver_falls_back_to_sample_in_development(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "environment", "development")
    mongo_repository = AsyncMock()
    mongo_repository.find_latest_by_field.return_value = None

    result = await CVDataResolver(mongo_repository).resolve("user-1")

    assert result.source == "sample_fallback"
    assert result.cv_data.user_name == SAMPLE_CV.user_name


@pytest.mark.asyncio
async def test_resolver_raises_in_production_without_cv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    mongo_repository = AsyncMock()
    mongo_repository.find_latest_by_field.return_value = None

    from src.domain.exceptions.cv_not_ready_error import CVNotReadyError

    with pytest.raises(CVNotReadyError):
        await CVDataResolver(mongo_repository).resolve("user-1")
