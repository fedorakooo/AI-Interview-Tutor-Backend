import pytest
from sqlalchemy import text
from src.api.dependencies.database import get_async_engine
from src.api.dependencies.redis import get_redis
from src.main import app


@pytest.mark.asyncio
async def test_lifespan_starts_and_closes_dependencies():
    async with app.router.lifespan_context(app):
        assert await get_redis().ping()
        async with get_async_engine().connect() as connection:
            assert (await connection.execute(text("SELECT 1"))).scalar_one() == 1
    assert get_async_engine().pool.checkedout() == 0
