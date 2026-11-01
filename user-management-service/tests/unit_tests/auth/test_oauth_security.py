from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from src.api.v1.endpoints import oauth
from src.domain.exceptions.login_errors import InvalidPasswordError
from src.domain.value_objects.user_role import UserRole


@pytest.fixture
def exchange(monkeypatch):
    client = AsyncMock()
    client.post.return_value = MagicMock(status_code=200)
    client.post.return_value.json.return_value = {"access_token": "provider-access"}
    transport = AsyncMock()
    transport.__aenter__.return_value = client
    monkeypatch.setattr(oauth.httpx, "AsyncClient", lambda **kwargs: transport)
    uow = AsyncMock()
    uow.user_repository = AsyncMock()
    user = SimpleNamespace(
        id=uuid4(),
        email="alice@example.com",
        username="alice",
        role=UserRole.USER,
        is_blocked=False,
        is_email_verified=True,
        mfa_secret=None,
        auth_version=4,
    )
    uow.user_repository.get_by_email.return_value = user
    access = MagicMock()
    access.generate_access_token.return_value = "access-token"
    refresh = MagicMock()
    refresh.generate_refresh_token.return_value = "refresh-token"
    redis = AsyncMock()

    async def run(provider, profile, *, emails=None, code=None):
        redis.getdel.return_value = provider
        responses = [MagicMock(status_code=200)]
        responses[0].json.return_value = profile
        if emails is not None:
            responses.append(MagicMock(status_code=200))
            responses[-1].json.return_value = emails
        client.get.side_effect = responses
        return await oauth._exchange_code_for_tokens(
            provider,
            {
                "token_url": "https://provider/token",
                "userinfo_url": "https://provider/profile",
                "client_id": "test-client",
                "client_secret": "test-secret",
            },
            "authorization-code",
            "state",
            uow,
            access,
            refresh,
            MagicMock(),
            redis,
            code,
        )

    return SimpleNamespace(run=run, user=user, uow=uow, client=client, access=access, refresh=refresh)


@pytest.mark.asyncio
async def test_google_rejects_unverified_email(exchange):
    with pytest.raises(HTTPException) as error:
        await exchange.run("google", {"email": "alice@example.com", "email_verified": False})
    assert error.value.status_code == 400
    exchange.uow.user_repository.get_by_email.assert_not_awaited()
    exchange.access.generate_access_token.assert_not_called()


@pytest.mark.asyncio
async def test_github_does_not_trust_public_profile_email(exchange):
    with pytest.raises(HTTPException) as error:
        await exchange.run(
            "github",
            {"email": "alice@example.com"},
            emails=[
                {"email": "alice@example.com", "primary": True, "verified": False},
            ],
        )
    assert error.value.status_code == 400
    exchange.uow.user_repository.get_by_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_verified_github_primary_email_and_account_version(exchange):
    result = await exchange.run(
        "github",
        {"email": "untrusted@example.com"},
        emails=[
            {"email": "alice@example.com", "primary": True, "verified": True},
        ],
    )
    assert result.token_type == "bearer"
    exchange.uow.user_repository.get_by_email.assert_awaited_once_with("alice@example.com")
    assert exchange.access.generate_access_token.call_args.kwargs["auth_version"] == 4
    assert exchange.refresh.generate_refresh_token.call_args.kwargs["auth_version"] == 4


@pytest.mark.asyncio
async def test_oauth_does_not_link_an_unverified_local_account(exchange):
    exchange.user.is_email_verified = False
    with pytest.raises(HTTPException) as error:
        await exchange.run("google", {"email": "alice@example.com", "email_verified": True})
    assert error.value.status_code == 409
    exchange.access.generate_access_token.assert_not_called()


@pytest.mark.asyncio
async def test_oauth_does_not_bypass_mfa(exchange):
    exchange.user.mfa_secret = "JBSWY3DPEHPK3PXP"
    with pytest.raises(InvalidPasswordError):
        await exchange.run("google", {"email": "alice@example.com", "email_verified": True})
    exchange.access.generate_access_token.assert_not_called()


@pytest.mark.asyncio
async def test_oauth_missing_provider_access_token_is_rejected(exchange):
    exchange.client.post.return_value.json.return_value = {"error": "invalid_grant"}
    with pytest.raises(HTTPException) as error:
        await exchange.run("google", {"email": "alice@example.com", "email_verified": True})
    assert error.value.status_code == 400
    exchange.client.get.assert_not_awaited()
