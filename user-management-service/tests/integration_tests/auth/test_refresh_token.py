import pytest
from jwt_handler.value_objects import TokenType
from src.api.dependencies.auth import get_token_handler


@pytest.mark.asyncio
async def test_refresh_token_success(test_client, sample_user_data):
    signup_response = await test_client.post("/api/v1/auth/signup", json=sample_user_data)
    assert signup_response.status_code == 201

    login_response = await test_client.post(
        "/api/v1/auth/token",
        data={
            "username": sample_user_data["username"],
            "password": sample_user_data["password"],
        },
    )
    assert login_response.status_code == 200
    refresh_token = login_response.json()["refresh_token"]

    response = await test_client.post("/api/v1/auth/refresh", data={"refresh_token": refresh_token})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert "auth_type" in data
    assert data["auth_type"] == "BEARER"


@pytest.mark.asyncio
async def test_refresh_token_invalid(test_client):
    response = await test_client.post("/api/v1/auth/refresh", data={"refresh_token": "invalid_token"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_expired(test_client, sample_user_data):
    signup_response = await test_client.post("/api/v1/auth/signup", json=sample_user_data)
    assert signup_response.status_code == 201
    user_id = signup_response.json()["id"]

    token_handler = get_token_handler()
    expired_token = token_handler.encode_jwt(
        payload={
            "id": user_id,
            "username": sample_user_data["username"],
            "type": TokenType.REFRESH,
        },
        expire_minutes=-1,
    )

    response = await test_client.post("/api/v1/auth/refresh", data={"refresh_token": expired_token})
    assert response.status_code == 401
