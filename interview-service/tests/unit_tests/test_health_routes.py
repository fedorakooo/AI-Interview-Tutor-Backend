from types import SimpleNamespace
from unittest.mock import AsyncMock

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
async def test_readiness_checks_and_shutdown(monkeypatch):
    pool = SimpleNamespace(check=AsyncMock())
    registry = SimpleNamespace(ping=AsyncMock(return_value=True))
    mongo = SimpleNamespace(admin=SimpleNamespace(command=AsyncMock()))
    manager = SimpleNamespace(is_shutting_down=False, accepting_connections=True, session_registry=registry)
    monkeypatch.setattr(app.state, "postgres_pool", pool, raising=False)
    monkeypatch.setattr(app.state, "mongo_client", mongo, raising=False)
    monkeypatch.setattr(app.state, "interview_manager", manager, raising=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/ready")
        assert response.status_code == 200
        assert response.json()["checks"] == {"postgres": "ok", "redis": "ok", "mongodb": "ok"}
        pool.check.assert_awaited_once()
        registry.ping.assert_awaited_once()
        mongo.admin.command.assert_awaited_once_with("ping")
        registry.ping.return_value = False
        assert (await client.get("/health/ready")).status_code == 503
        manager.is_shutting_down = True
        response = await client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "shutting_down"
