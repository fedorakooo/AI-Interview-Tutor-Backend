from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from httpx import ASGITransport, AsyncClient
from src.main import app


@pytest.mark.asyncio
async def test_health_and_removed_metrics_route():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert "x-correlation-id" not in response.headers
        assert (await client.get("/metrics")).status_code == 404
    assert "/metrics" not in app.openapi()["paths"]


@pytest.mark.asyncio
async def test_readiness_keeps_mongo_and_rabbitmq_checks(monkeypatch):
    mongo = SimpleNamespace(admin=SimpleNamespace(command=AsyncMock()))
    rabbitmq_check = Mock()
    monkeypatch.setattr(app.state, "mongo_client", mongo, raising=False)
    monkeypatch.setattr("src.infrastructure.rabbitmq.consumers.wait_for_rabbitmq", rabbitmq_check)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/ready")
        assert response.status_code == 200
        assert response.json()["checks"] == {"mongodb": "ok", "rabbitmq": "ok"}
        mongo.admin.command.assert_awaited_once_with("ping")
        rabbitmq_check.assert_called_once_with(timeout=2.0)
        rabbitmq_check.side_effect = TimeoutError("unavailable")
        assert (await client.get("/ready")).status_code == 503
