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
async def test_requests_are_no_longer_limited_by_removed_middleware():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(181):
            assert (await client.get("/api/v1/removed-middleware-check")).status_code == 404
