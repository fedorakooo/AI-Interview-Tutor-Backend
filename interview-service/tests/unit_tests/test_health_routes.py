from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from src.main import app


@pytest.mark.asyncio
async def test_health_route_and_removed_legacy_routes():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        for path in ("/", "/static/interview_client.html", "/api/v1/interview/sessions", "/metrics"):
            assert (await client.get(path)).status_code == 404


@pytest.mark.asyncio
async def test_readiness_checks_redis_and_mongo(monkeypatch):
    redis = SimpleNamespace(ping=AsyncMock(return_value=True))
    mongo = SimpleNamespace(admin=SimpleNamespace(command=AsyncMock()))
    monkeypatch.setattr(app.state, "redis_client", redis, raising=False)
    monkeypatch.setattr(app.state, "mongo_client", mongo, raising=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/ready")
        assert response.status_code == 200
        assert response.json()["checks"] == {"redis": "ok", "mongodb": "ok"}
        mongo.admin.command.assert_awaited_once_with("ping")

        redis.ping.return_value = False
        response = await client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["checks"]["redis"] == "unavailable"

        redis.ping.side_effect = ConnectionError("redis down")
        assert (await client.get("/health/ready")).status_code == 503
