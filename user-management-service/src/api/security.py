from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, OAuth2PasswordBearer
from jwt_handler.interfaces import ITokenHandler
from jwt_handler.value_objects import AccessTokenPayload

from src.api.dependencies.auth import get_token_handler
from src.domain.exceptions.user_errors import UserBlockedError
from src.domain.value_objects.user_role import UserRole

http_bearer = HTTPBearer(auto_error=False)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/token",
)


async def get_access_token_payload(
    token_handler: Annotated[ITokenHandler, Depends(get_token_handler)],
    token: str = Depends(oauth2_scheme),
) -> AccessTokenPayload:
    return token_handler.decode_jwt(token)


async def require_authenticated(
    payload: Annotated[AccessTokenPayload, Depends(get_access_token_payload)],
) -> AccessTokenPayload:
    if payload.get("is_blocked"):
        raise UserBlockedError(payload["username"])
    return payload


def require_roles(*roles: UserRole):
    async def _check(
        payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    ) -> AccessTokenPayload:
        if payload["role"] not in {role.value for role in roles}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return payload

    return _check
