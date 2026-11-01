from typing import NotRequired, TypedDict

from jwt_handler.value_objects.auth_type import TokenType


class AccessTokenPayload(TypedDict):
    auth_version: NotRequired[int]
    id: str
    username: str
    role: str
    is_blocked: bool
    type: TokenType


class RefreshTokenPayload(TypedDict):
    auth_version: NotRequired[int]
    id: str
    username: str
    type: TokenType
