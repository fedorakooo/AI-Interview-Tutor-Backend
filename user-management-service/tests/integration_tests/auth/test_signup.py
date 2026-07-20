import pytest

from tests.conftest import faker


@pytest.mark.asyncio
async def test_signup_success(test_client, sample_user_data):
    response = await test_client.post("/api/v1/auth/signup", json=sample_user_data)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == sample_user_data["email"]
    assert data["username"] == sample_user_data["username"]
    assert data["first_name"] == sample_user_data["first_name"]
    assert data["second_name"] == sample_user_data["second_name"]
    assert "id" in data


@pytest.mark.asyncio
async def test_signup_duplicate_email(test_client, sample_user_data):
    first_response = await test_client.post(
        "/api/v1/auth/signup",
        json={
            **sample_user_data,
        },
    )

    assert first_response.status_code == 201

    second_response = await test_client.post(
        "/api/v1/auth/signup",
        json={
            **sample_user_data,
            "username": faker.user_name(),
            "phone_number": faker.phone_number(),
        },
    )
    assert second_response.status_code == 400


@pytest.mark.asyncio
async def test_signup_duplicate_phone_number(test_client, sample_user_data):
    first_response = await test_client.post(
        "/api/v1/auth/signup",
        json={
            **sample_user_data,
        },
    )

    assert first_response.status_code == 201

    second_response = await test_client.post(
        "/api/v1/auth/signup",
        json={
            **sample_user_data,
            "username": faker.user_name(),
            "email": faker.email(),
        },
    )
    assert second_response.status_code == 400


@pytest.mark.asyncio
async def test_signup_duplicate_username(test_client, sample_user_data):
    response = await test_client.post(
        "/api/v1/auth/signup",
        json={
            **sample_user_data,
            "email": faker.email(),
            "phone_number": faker.phone_number(),
        },
    )
    assert response.status_code == 201

    response = await test_client.post(
        "/api/v1/auth/signup",
        json={
            **sample_user_data,
            "email": faker.email(),
            "phone_number": faker.phone_number(),
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_signup_invalid_data_email(test_client):
    response = await test_client.post(
        "/api/v1/auth/signup",
        json={
            "email": "invalid-email",
            "password": faker.password(),
            "username": faker.user_name(),
            "first_name": faker.first_name(),
            "second_name": faker.last_name(),
            "phone_number": faker.phone_number(),
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_signup_invalid_data_phone_number(test_client):
    response = await test_client.post(
        "/api/v1/auth/signup",
        json={
            "email": faker.email(),
            "password": faker.password(),
            "username": faker.user_name(),
            "name": faker.first_name(),
            "surname": faker.last_name(),
            "phone_number": "invalid-phone-number",
            "group_id": None,
        },
    )
    assert response.status_code == 422
