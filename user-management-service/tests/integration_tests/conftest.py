from datetime import datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from src.api.dependencies.redis import get_redis
from src.main import app

from tests.conftest import faker
from tests.integration_tests.test_db import drop_db, init_db


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    try:
        await init_db()
        yield
    finally:
        await drop_db()


@pytest_asyncio.fixture
async def test_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as client:
        yield client


@pytest_asyncio.fixture(autouse=True)
async def setup_redis():
    redis = get_redis()
    try:
        yield
    finally:
        await redis.aclose()


@pytest.fixture
def sample_now() -> datetime:
    return datetime.now()


@pytest.fixture
def sample_user_data():
    return {
        "email": faker.email(),
        "password": faker.password(),
        "username": faker.user_name(),
        "first_name": faker.first_name(),
        "second_name": faker.last_name(),
        "phone_number": faker.phone_number(),
    }
