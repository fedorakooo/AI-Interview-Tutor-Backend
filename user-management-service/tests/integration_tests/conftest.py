from datetime import datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from src.api.dependencies.redis import get_redis
from src.main import app

from tests.conftest import faker
from tests.integration_tests.test_db import drop_db, init_db


def _valid_name() -> str:
    """Faker ru_RU can emit 2-letter names; API requires 3–30 chars."""
    for _ in range(20):
        name = faker.first_name().strip()
        if 3 <= len(name) <= 30:
            return name
    return "Иван"


def _valid_last_name() -> str:
    for _ in range(20):
        name = faker.last_name().strip()
        if 3 <= len(name) <= 30:
            return name
    return "Иванов"


def _valid_username() -> str:
    """Username must be 4–30 chars, alphanumeric/._ without edge dots."""
    for _ in range(20):
        username = faker.user_name().replace("-", "_")
        if (
            4 <= len(username) <= 30
            and username[0] not in "._"
            and username[-1] not in "._"
            and ".." not in username
            and "__" not in username
            and "._" not in username
            and "_." not in username
        ):
            return username
    return f"user_{faker.random_int(min=1000, max=9999)}"


def _valid_password() -> str:
    for _ in range(20):
        password = faker.password(length=12)
        if 8 <= len(password) <= 128 and any(ch.isdigit() for ch in password):
            return password
    return "Password1!"


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
        "password": _valid_password(),
        "username": _valid_username(),
        "first_name": _valid_name(),
        "second_name": _valid_last_name(),
        "phone_number": faker.phone_number(),
    }
