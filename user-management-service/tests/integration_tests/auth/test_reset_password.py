import pytest

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

    reset_response = await test_client.post("/api/v1/auth/reset-password", data={"email": sample_user_data["email"]})
    assert reset_response.status_code == 200
    reset_token = reset_response.json()["password_reset_token"]

    invalid_token = reset_token[:-1] + "X"

    response = await test_client.post(
        f"/api/v1/auth/reset-password/{invalid_token}",
        json={"new_password": faker.password()},
    )
    assert response.status_code == 404
