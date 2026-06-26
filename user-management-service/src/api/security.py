from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPBearer, OAuth2PasswordBearer
from jwt_handler.interfaces import ITokenHandler
from jwt_handler.value_objects import AccessTokenPayload

from src.api.dependencies.auth import get_token_handler

http_bearer = HTTPBearer(auto_error=False)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/token",
)


async def get_access_token_payload(
    token_handler: Annotated[ITokenHandler, Depends(get_token_handler)],
    token: str = Depends(oauth2_scheme),
) -> AccessTokenPayload:
    return token_handler.decode_jwt(token)
