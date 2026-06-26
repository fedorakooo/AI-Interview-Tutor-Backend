import pytest

from tests.conftest import faker


@pytest.mark.asyncio
async def test_login_success(test_client, sample_user_data):
    signup_response = await test_client.post("/api/v1/auth/signup", json=sample_user_data)
    assert signup_response.status_code == 201

    response = await test_client.post(
        "/api/v1/auth/login",
        data={
            "username": sample_user_data["username"],
            "password": sample_user_data["password"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert "auth_type" in data
    assert data["auth_type"] == "BEARER"


@pytest.mark.asyncio
async def test_login_invalid_credentials(test_client):
    response = await test_client.post(
        "/api/v1/auth/login",
        data={"username": faker.user_name(), "password": faker.password()},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_invalid_username(test_client, sample_user_data):
    signup_response = await test_client.post("/api/v1/auth/signup", json=sample_user_data)
    assert signup_response.status_code == 201

    response = await test_client.post(
        "/api/v1/auth/login",
        data={"username": faker.user_name(), "password": sample_user_data["password"]},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_invalid_password(test_client, sample_user_data):
    signup_response = await test_client.post("/api/v1/auth/signup", json=sample_user_data)
    assert signup_response.status_code == 201

    response = await test_client.post(
        "/api/v1/auth/login",
        data={"username": sample_user_data["username"], "password": faker.password()},
    )
    assert response.status_code == 401
