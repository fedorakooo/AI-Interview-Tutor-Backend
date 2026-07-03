from typing import Annotated

from fastapi import Depends, HTTPException, status
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
