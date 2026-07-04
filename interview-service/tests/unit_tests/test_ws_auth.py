from uuid import UUID, uuid4

import pytest
from fastapi import WebSocketException
from jwt_handler.handlers import JWTTokenHandler
from jwt_handler.value_objects import AccessTokenPayload, TokenType

from src.api.security import verify_ws_token


@pytest.mark.asyncio
async def test_verify_ws_token_valid(token_handler: JWTTokenHandler, user_id: str, access_token: str):
    payload = await verify_ws_token(
        user_id=UUID(user_id),
        token=access_token,
        token_handler=token_handler,
    )
    assert payload["id"] == user_id


@pytest.mark.asyncio
async def test_verify_ws_token_user_mismatch(token_handler: JWTTokenHandler, access_token: str):
    with pytest.raises(WebSocketException) as exc_info:
        await verify_ws_token(
            user_id=uuid4(),
            token=access_token,
            token_handler=token_handler,
        )
    assert exc_info.value.code == 1008


@pytest.mark.asyncio
async def test_verify_ws_token_invalid(token_handler: JWTTokenHandler, user_id: str):
    with pytest.raises(WebSocketException) as exc_info:
        await verify_ws_token(
            user_id=UUID(user_id),
            token="invalid.token.value",
            token_handler=token_handler,
        )
    assert exc_info.value.code == 1008


@pytest.mark.asyncio
async def test_verify_ws_token_blocked_user(token_handler: JWTTokenHandler, user_id: str):
    blocked_payload = AccessTokenPayload(
        id=user_id,
        username="blocked",
        role="USER",
        is_blocked=True,
        type=TokenType.ACCESS,
    )
    blocked_token = token_handler.encode_jwt(payload=blocked_payload, expire_minutes=30)

    with pytest.raises(WebSocketException) as exc_info:
        await verify_ws_token(
            user_id=UUID(user_id),
            token=blocked_token,
            token_handler=token_handler,
        )
    assert exc_info.value.code == 1008


@pytest.mark.asyncio
async def test_verify_ws_token_wrong_type(token_handler: JWTTokenHandler, user_id: str):
    refresh_payload = AccessTokenPayload(
        id=user_id,
        username="testuser",
        role="USER",
        is_blocked=False,
        type=TokenType.REFRESH,
    )
    refresh_token = token_handler.encode_jwt(payload=refresh_payload, expire_minutes=30)

    with pytest.raises(WebSocketException) as exc_info:
        await verify_ws_token(
            user_id=UUID(user_id),
            token=refresh_token,
            token_handler=token_handler,
        )
    assert exc_info.value.code == 1008
