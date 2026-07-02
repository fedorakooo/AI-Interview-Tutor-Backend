from typing import Annotated
from uuid import UUID

from fastapi import Depends, Query, WebSocketException, status
from jwt_handler.exceptions.token_errors import TokenError
from jwt_handler.interfaces import ITokenHandler
from jwt_handler.value_objects import AccessTokenPayload, TokenType

from src.api.dependencies.auth import get_token_handler


async def verify_ws_token(
    user_id: UUID,
    token_handler: Annotated[ITokenHandler, Depends(get_token_handler)],
    token: str = Query(...),
) -> AccessTokenPayload:
    try:
        payload = token_handler.decode_jwt(token)
    except TokenError as exc:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason=str(exc)) from exc

    if payload.get("type") != TokenType.ACCESS:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid token type",
        )

    if payload.get("is_blocked"):
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="User is blocked",
        )

    if payload.get("id") != str(user_id):
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Token user mismatch",
        )

    return payload
