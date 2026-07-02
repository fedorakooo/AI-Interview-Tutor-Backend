from uuid import UUID

import pytest
from jwt_handler.value_objects import AccessTokenPayload, TokenType
from sqlalchemy import update

from src.api.dependencies.auth import get_token_handler
from src.domain.value_objects.user_role import UserRole
from src.infrastructure.postgres.schemas.user import UserORM
from tests.integration_tests.test_db import engine


async def _signup_and_get_token(test_client, sample_user_data) -> tuple[str, UUID]:
    signup_response = await test_client.post("/api/v1/auth/signup", json=sample_user_data)
    assert signup_response.status_code == 201
    user_id = UUID(signup_response.json()["id"])

    token_response = await test_client.post(
        "/api/v1/auth/token",
        data={
            "username": sample_user_data["username"],
            "password": sample_user_data["password"],
        },
    )
    assert token_response.status_code == 200
    return token_response.json()["access_token"], user_id


async def _set_user_role(user_id: UUID, role: UserRole) -> None:
    async with engine.begin() as conn:
        await conn.execute(update(UserORM).where(UserORM.id == user_id).values(role=role))


def _blocked_user_token(user_id: UUID, username: str) -> str:
    token_handler = get_token_handler()
    payload = AccessTokenPayload(
        id=str(user_id),
        username=username,
        role=UserRole.USER.value,
        is_blocked=True,
        type=TokenType.ACCESS,
    )
    return token_handler.encode_jwt(payload=payload, expire_minutes=30)


@pytest.mark.asyncio
async def test_get_users_without_token_returns_401(test_client):
    response = await test_client.get("/api/v1/users")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_users_with_user_role_returns_403(test_client, sample_user_data):
    access_token, _ = await _signup_and_get_token(test_client, sample_user_data)

    response = await test_client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_users_with_admin_role_returns_200(test_client, sample_user_data):
    access_token, user_id = await _signup_and_get_token(test_client, sample_user_data)
    await _set_user_role(user_id, UserRole.ADMIN)

    admin_token_response = await test_client.post(
        "/api/v1/auth/token",
        data={
            "username": sample_user_data["username"],
            "password": sample_user_data["password"],
        },
    )
    assert admin_token_response.status_code == 200
    admin_token = admin_token_response.json()["access_token"]

    response = await test_client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_me_without_token_returns_401(test_client):
    response = await test_client.get("/api/v1/user/me/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_with_blocked_token_returns_403(test_client, sample_user_data):
    signup_response = await test_client.post("/api/v1/auth/signup", json=sample_user_data)
    assert signup_response.status_code == 201
    user_id = UUID(signup_response.json()["id"])

    blocked_token = _blocked_user_token(user_id, sample_user_data["username"])

    response = await test_client.get(
        "/api/v1/user/me/",
        headers={"Authorization": f"Bearer {blocked_token}"},
    )
    assert response.status_code == 403
