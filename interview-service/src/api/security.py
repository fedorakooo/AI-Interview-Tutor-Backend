from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Query, WebSocketException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt_handler.exceptions.token_errors import TokenError
from jwt_handler.interfaces import ITokenHandler
from jwt_handler.value_objects import AccessTokenPayload, TokenType

from src.api.dependencies.auth import get_token_handler

http_bearer = HTTPBearer(auto_error=False)


async def get_access_token_payload(
    token_handler: Annotated[ITokenHandler, Depends(get_token_handler)],
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
) -> AccessTokenPayload:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    try:
        return token_handler.decode_jwt(credentials.credentials)
    except TokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


async def require_authenticated(
    payload: Annotated[AccessTokenPayload, Depends(get_access_token_payload)],
) -> AccessTokenPayload:
    if payload.get("type") != TokenType.ACCESS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    if payload.get("is_blocked"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is blocked")
    return payload


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
