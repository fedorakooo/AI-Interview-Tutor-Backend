from typing import cast

import pytest
from jwt_handler.value_objects import RefreshTokenPayload
from src.api.dependencies.auth import get_token_handler
from src.application.use_cases.auth.request_reset_password_use_case import PASSWORD_RESET_TOKEN_TYPE

from tests.conftest import faker


@pytest.mark.asyncio
async def test_reset_password_success(test_client, sample_user_data):
    signup_response = await test_client.post("/api/v1/auth/signup", json=sample_user_data)
    assert signup_response.status_code == 201

    response = await test_client.post("/api/v1/auth/reset-password", data={"email": sample_user_data["email"]})
    assert response.status_code == 200
    data = response.json()
    assert "password_reset_token" in data


@pytest.mark.asyncio
async def test_reset_password_nonexistent_email(test_client):
    response = await test_client.post("/api/v1/auth/reset-password", data={"email": faker.email()})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_reset_password_by_key_invalid_token(test_client):
    response = await test_client.post(
        "/api/v1/auth/reset-password/invalid-token",
        json={"new_password": faker.password()},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_reset_password_by_key_expired_token(test_client, sample_user_data):
    signup_response = await test_client.post("/api/v1/auth/signup", json=sample_user_data)
    assert signup_response.status_code == 201
    user_id = signup_response.json()["id"]

    token_handler = get_token_handler()
    payload = cast(
        RefreshTokenPayload,
        {
            "id": user_id,
            "username": sample_user_data["email"],
            "type": PASSWORD_RESET_TOKEN_TYPE,
        },
    )
    expired_token = token_handler.encode_jwt(payload, expire_minutes=-1)

    response = await test_client.post(
        f"/api/v1/auth/reset-password/{expired_token}",
        json={"new_password": faker.password()},
    )
    assert response.status_code == 404
