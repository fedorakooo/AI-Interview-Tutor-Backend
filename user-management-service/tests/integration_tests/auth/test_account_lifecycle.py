import asyncio
import base64
import hashlib
import hmac
import json
import struct
import time
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from sqlalchemy import update
from src.api.dependencies.auth import get_token_handler
from src.api.dependencies.rabbitmq import get_email_verify_producer, get_reset_password_producer
from src.application.use_cases.auth.email_verification_use_case import EMAIL_VERIFY_TOKEN_TYPE
from src.application.use_cases.auth.request_reset_password_use_case import PASSWORD_RESET_TOKEN_TYPE
from src.domain.value_objects.user_role import UserRole
from src.infrastructure.postgres.schemas.user import UserORM
from src.main import app

from tests.integration_tests.test_db import engine

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mailbox():
    messages = []

    async def send(message):
        messages.append(json.loads(message))

    producer = AsyncMock()
    producer.send_message.side_effect = send
    app.dependency_overrides[get_email_verify_producer] = lambda: producer
    app.dependency_overrides[get_reset_password_producer] = lambda: producer
    yield messages
    app.dependency_overrides.pop(get_email_verify_producer, None)
    app.dependency_overrides.pop(get_reset_password_producer, None)


async def signup_and_login(client, data):
    signup = await client.post("/api/v1/auth/signup", json=data)
    assert signup.status_code == 201
    response = await client.post(
        "/api/v1/auth/token",
        data={
            "username": data["username"],
            "password": data["password"],
        },
    )
    assert response.status_code == 200
    return signup.json(), response.json()


def bearer(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def email_token(mailbox):
    return mailbox[-1]["body"].split("?token=", 1)[1]


async def set_account(user_id, **values):
    async with engine.begin() as conn:
        await conn.execute(update(UserORM).where(UserORM.id == UUID(user_id)).values(**values))


def totp(secret):
    key = base64.b32decode(secret + "=" * ((8 - len(secret) % 8) % 8))
    digest = hmac.new(key, struct.pack(">Q", int(time.time()) // 30), hashlib.sha1).digest()
    offset = digest[-1] & 15
    number = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % 1000000
    return f"{number:06d}"


async def test_refresh_race_has_one_winner_and_rotated_token_works(test_client, sample_user_data, mailbox):
    _, tokens = await signup_and_login(test_client, sample_user_data)
    old = tokens["refresh_token"]
    results = await asyncio.gather(
        *[test_client.post("/api/v1/auth/refresh", data={"refresh_token": old}) for _ in range(2)]
    )
    assert sorted(r.status_code for r in results) == [200, 401]
    rotated = next(r.json() for r in results if r.status_code == 200)
    assert rotated["refresh_token"] != old
    assert rotated["token_type"] == "bearer"
    again = await test_client.post("/api/v1/auth/refresh", data={"refresh_token": rotated["refresh_token"]})
    assert again.status_code == 200
    assert again.json()["refresh_token"] != rotated["refresh_token"]


async def test_independent_logins_and_logout(test_client, sample_user_data, mailbox):
    _, first = await signup_and_login(test_client, sample_user_data)
    second = await test_client.post(
        "/api/v1/auth/token",
        data={
            "username": sample_user_data["username"],
            "password": sample_user_data["password"],
        },
    )
    second = second.json()
    assert first["refresh_token"] != second["refresh_token"]
    for _ in range(2):
        response = await test_client.post("/api/v1/auth/logout", data={"refresh_token": first["refresh_token"]})
        assert response.status_code == 200
    revoked = await test_client.post("/api/v1/auth/refresh", data={"refresh_token": first["refresh_token"]})
    assert revoked.status_code == 401
    live = await test_client.post("/api/v1/auth/refresh", data={"refresh_token": second["refresh_token"]})
    assert live.status_code == 200


async def test_change_password_revokes_all_previous_credentials(test_client, sample_user_data, mailbox):
    _, tokens = await signup_and_login(test_client, sample_user_data)
    changed = await test_client.post(
        "/api/v1/auth/change-password",
        headers=bearer(tokens),
        json={
            "current_password": sample_user_data["password"],
            "new_password": "ChangedPassword2!",
        },
    )
    assert changed.status_code == 200
    assert (await test_client.get("/api/v1/user/me/", headers=bearer(tokens))).status_code == 401
    assert (
        await test_client.post(
            "/api/v1/auth/refresh",
            data={
                "refresh_token": tokens["refresh_token"],
            },
        )
    ).status_code == 401
    assert (
        await test_client.post(
            "/api/v1/auth/token",
            data={
                "username": sample_user_data["username"],
                "password": sample_user_data["password"],
            },
        )
    ).status_code == 401
    login = await test_client.post(
        "/api/v1/auth/token",
        data={
            "username": sample_user_data["username"],
            "password": "ChangedPassword2!",
        },
    )
    assert login.status_code == 200
    assert (await test_client.get("/api/v1/user/me/", headers=bearer(login.json()))).status_code == 200
    refresh = await test_client.post("/api/v1/auth/refresh", data={"refresh_token": login.json()["refresh_token"]})
    assert refresh.status_code == 200


async def test_wrong_current_password_preserves_session(test_client, sample_user_data, mailbox):
    _, tokens = await signup_and_login(test_client, sample_user_data)
    response = await test_client.post(
        "/api/v1/auth/change-password",
        headers=bearer(tokens),
        json={
            "current_password": "WrongPassword1!",
            "new_password": "ChangedPassword2!",
        },
    )
    assert response.status_code == 401
    assert (await test_client.get("/api/v1/user/me/", headers=bearer(tokens))).status_code == 200


async def test_reset_token_is_single_use_under_race(test_client, sample_user_data, mailbox):
    _, tokens = await signup_and_login(test_client, sample_user_data)
    response = await test_client.post("/api/v1/auth/reset-password", data={"email": sample_user_data["email"]})
    assert response.status_code == 200
    reset = email_token(mailbox)
    results = await asyncio.gather(
        *[
            test_client.post(f"/api/v1/auth/reset-password/{reset}", json={"new_password": "ResetPassword3!"})
            for _ in range(2)
        ]
    )
    assert sorted(r.status_code for r in results) == [200, 404]
    assert (await test_client.get("/api/v1/user/me/", headers=bearer(tokens))).status_code == 401
    assert (
        await test_client.post(
            "/api/v1/auth/refresh",
            data={
                "refresh_token": tokens["refresh_token"],
            },
        )
    ).status_code == 401
    assert (
        await test_client.post(
            "/api/v1/auth/token",
            data={
                "username": sample_user_data["username"],
                "password": "ResetPassword3!",
            },
        )
    ).status_code == 200


async def test_reset_response_does_not_disclose_email(test_client, sample_user_data, mailbox):
    user, _ = await signup_and_login(test_client, sample_user_data)
    responses = []
    for email in (sample_user_data["email"], "absent@example.com"):
        response = await test_client.post("/api/v1/auth/reset-password", data={"email": email})
        assert response.status_code == 200
        responses.append(response.json())
    await set_account(user["id"], is_blocked=True)
    response = await test_client.post("/api/v1/auth/reset-password", data={"email": sample_user_data["email"]})
    assert response.status_code == 200
    assert responses[0] == responses[1] == response.json()
    assert len(mailbox) == 2  # Signup verification plus one reset for the active account.


async def test_verify_email_race_and_address_change(test_client, sample_user_data, mailbox):
    _, tokens = await signup_and_login(test_client, sample_user_data)
    token = email_token(mailbox)
    results = await asyncio.gather(*[test_client.post(f"/api/v1/auth/verify-email/{token}") for _ in range(2)])
    assert sorted(r.status_code for r in results) == [200, 404]
    me = await test_client.get("/api/v1/user/me/", headers=bearer(tokens))
    assert me.json()["is_email_verified"] is True
    changed = await test_client.patch("/api/v1/user/me/", headers=bearer(tokens), json={"email": "new@example.com"})
    assert changed.status_code == 200
    assert changed.json()["is_email_verified"] is False
    assert (await test_client.post(f"/api/v1/auth/verify-email/{token}")).status_code == 404
    assert (await test_client.get("/api/v1/user/me/", headers=bearer(tokens))).status_code == 401
    login = await test_client.post(
        "/api/v1/auth/token",
        data={"username": sample_user_data["username"], "password": sample_user_data["password"]},
    )
    assert login.status_code == 200
    tokens = login.json()
    assert (await test_client.post("/api/v1/auth/verify-email", headers=bearer(tokens))).status_code == 200
    new = email_token(mailbox)
    assert get_token_handler().decode_jwt(new)["username"] == "new@example.com"
    assert (await test_client.post(f"/api/v1/auth/verify-email/{new}")).status_code == 200


async def test_email_change_invalidates_old_reset_and_verification_links(test_client, sample_user_data, mailbox):
    _, tokens = await signup_and_login(test_client, sample_user_data)
    verification = email_token(mailbox)
    await test_client.post("/api/v1/auth/reset-password", data={"email": sample_user_data["email"]})
    reset = email_token(mailbox)
    changed = await test_client.patch("/api/v1/user/me/", headers=bearer(tokens), json={"email": "new@example.com"})
    assert changed.status_code == 200
    assert (await test_client.post(f"/api/v1/auth/verify-email/{verification}")).status_code == 404
    assert (
        await test_client.post(
            f"/api/v1/auth/reset-password/{reset}",
            json={
                "new_password": "ResetPassword3!",
            },
        )
    ).status_code == 404

    login = await test_client.post(
        "/api/v1/auth/token",
        data={"username": sample_user_data["username"], "password": sample_user_data["password"]},
    )
    assert login.status_code == 200
    restored = await test_client.patch(
        "/api/v1/user/me/", headers=bearer(login.json()), json={"email": sample_user_data["email"]}
    )
    assert restored.status_code == 200
    assert (await test_client.post(f"/api/v1/auth/verify-email/{verification}")).status_code == 404
    assert (
        await test_client.post(f"/api/v1/auth/reset-password/{reset}", json={"new_password": "ResetPassword3!"})
    ).status_code == 404


@pytest.mark.parametrize("kind", [PASSWORD_RESET_TOKEN_TYPE, EMAIL_VERIFY_TOKEN_TYPE])
async def test_malformed_signed_account_links_return_404(test_client, kind):
    token = get_token_handler().encode_jwt({"type": kind, "id": "not-a-uuid"}, expire_minutes=5)
    route = "reset-password" if kind == PASSWORD_RESET_TOKEN_TYPE else "verify-email"
    response = await test_client.post(f"/api/v1/auth/{route}/{token}", json={"new_password": "ResetPassword3!"})
    assert response.status_code == 404


async def test_block_and_unblock_do_not_restore_old_tokens(test_client, sample_user_data, mailbox):
    user, tokens = await signup_and_login(test_client, sample_user_data)
    # Exercise the actual administrator endpoint with the same access JWT after a role promotion.
    await set_account(user["id"], role=UserRole.ADMIN)
    blocked = await test_client.patch(f"/api/v1/user/{user['id']}", headers=bearer(tokens), json={"is_blocked": True})
    assert blocked.status_code == 200
    assert (await test_client.get("/api/v1/user/me/", headers=bearer(tokens))).status_code == 403
    assert (
        await test_client.post(
            "/api/v1/auth/refresh",
            data={
                "refresh_token": tokens["refresh_token"],
            },
        )
    ).status_code == 403
    await set_account(user["id"], is_blocked=False)
    assert (await test_client.get("/api/v1/user/me/", headers=bearer(tokens))).status_code == 401
    assert (
        await test_client.post(
            "/api/v1/auth/refresh",
            data={
                "refresh_token": tokens["refresh_token"],
            },
        )
    ).status_code == 401


async def test_current_roles_search_and_account_deletion(test_client, sample_user_data, mailbox):
    user, tokens = await signup_and_login(test_client, sample_user_data)
    assert (await test_client.get("/api/v1/users", headers=bearer(tokens))).status_code == 403
    await set_account(user["id"], role=UserRole.ADMIN)
    result = await test_client.get(
        "/api/v1/users",
        headers=bearer(tokens),
        params={
            "filter_by_name": sample_user_data["first_name"],
            "limit": 1,
        },
    )
    assert result.status_code == 200
    assert result.json()["total"] == 1
    assert result.json()["users"][0]["id"] == user["id"]
    assert "hashed_password" not in result.json()["users"][0]
    await set_account(user["id"], role=UserRole.USER)
    assert (await test_client.get("/api/v1/users", headers=bearer(tokens))).status_code == 403
    deleted = await test_client.delete("/api/v1/user/me/", headers=bearer(tokens))
    assert deleted.status_code == 204
    assert not deleted.content
    assert (await test_client.get("/api/v1/user/me/", headers=bearer(tokens))).status_code == 401
    assert (
        await test_client.post(
            "/api/v1/auth/refresh",
            data={
                "refresh_token": tokens["refresh_token"],
            },
        )
    ).status_code == 401


async def test_refresh_cannot_be_used_at_any_account_endpoint(test_client, sample_user_data, mailbox):
    _, tokens = await signup_and_login(test_client, sample_user_data)
    headers = {"Authorization": f"Bearer {tokens['refresh_token']}"}
    for path in ("/api/v1/user/me/", "/api/v1/users", "/api/v1/privacy/export"):
        response = await test_client.get(path, headers=headers)
        assert response.status_code == 401
    assert (await test_client.post("/api/v1/auth/verify-email", headers=headers)).status_code == 401
    assert (
        await test_client.post(
            "/api/v1/auth/logout",
            data={
                "refresh_token": tokens["access_token"],
            },
        )
    ).status_code == 401


async def test_mfa_is_required_before_login_token_issuance(test_client, sample_user_data, mailbox):
    user, tokens = await signup_and_login(test_client, sample_user_data)
    await set_account(user["id"], role=UserRole.ADMIN)
    setup = await test_client.post("/api/v1/auth/mfa/setup", headers=bearer(tokens))
    assert setup.status_code == 200
    secret = setup.json()["secret"]
    assert (await test_client.get("/api/v1/user/me/", headers=bearer(tokens))).status_code == 401
    assert (
        await test_client.post(
            "/api/v1/auth/refresh",
            data={
                "refresh_token": tokens["refresh_token"],
            },
        )
    ).status_code == 401
    credentials = {"username": sample_user_data["username"], "password": sample_user_data["password"]}
    assert (await test_client.post("/api/v1/auth/token", data=credentials)).status_code == 401
    invalid = {**credentials, "totp_code": "invalid"}
    assert (await test_client.post("/api/v1/auth/token", data=invalid)).status_code == 401
    login = await test_client.post("/api/v1/auth/token", data={**credentials, "totp_code": totp(secret)})
    assert login.status_code == 200
    headers = bearer(login.json())
    assert (
        await test_client.post(
            "/api/v1/auth/mfa/verify",
            headers=headers,
            json={
                "code": totp(secret),
            },
        )
    ).status_code == 200
    assert (await test_client.post("/api/v1/auth/mfa/setup", headers=headers)).status_code == 409


@pytest.mark.parametrize("password", ["a" * 72 + "1", "я" * 36 + "1"])
async def test_bcrypt_byte_limit_is_validated(test_client, sample_user_data, password):
    response = await test_client.post("/api/v1/auth/signup", json={**sample_user_data, "password": password})
    assert response.status_code == 422


async def test_wrong_password_is_not_printed(test_client, sample_user_data, mailbox, capsys):
    await signup_and_login(test_client, sample_user_data)
    wrong = "NeverPrintThisPassword123!"
    response = await test_client.post(
        "/api/v1/auth/token",
        data={
            "username": sample_user_data["username"],
            "password": wrong,
        },
    )
    assert response.status_code == 401
    output = capsys.readouterr()
    assert wrong not in output.out + output.err


async def test_deletion_with_retained_references_returns_conflict(test_client, sample_user_data, mailbox):
    from uuid import uuid4

    from sqlalchemy import insert
    from src.infrastructure.postgres.schemas.organization import OrganizationORM

    user, tokens = await signup_and_login(test_client, sample_user_data)
    async with engine.begin() as conn:
        await conn.execute(
            insert(OrganizationORM).values(
                id=uuid4(),
                name="Retained organization",
                owner_user_id=UUID(user["id"]),
            )
        )
    result = await test_client.delete("/api/v1/user/me/", headers=bearer(tokens))
    assert result.status_code == 409
    assert (await test_client.get("/api/v1/user/me/", headers=bearer(tokens))).status_code == 200


async def test_reset_queue_failure_does_not_disclose_account(test_client, sample_user_data, mailbox):
    await signup_and_login(test_client, sample_user_data)
    producer = app.dependency_overrides[get_reset_password_producer]()
    producer.send_message.side_effect = ConnectionError("Notification service unavailable")
    known = await test_client.post("/api/v1/auth/reset-password", data={"email": sample_user_data["email"]})
    absent = await test_client.post("/api/v1/auth/reset-password", data={"email": "absent@example.com"})
    assert known.status_code == absent.status_code == 200
    assert known.json() == absent.json()
