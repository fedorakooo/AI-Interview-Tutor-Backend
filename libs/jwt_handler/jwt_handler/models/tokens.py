from typing import Literal

from pydantic import BaseModel

from jwt_handler.dtos import TokenInfoDTO
from jwt_handler.value_objects import AuthType


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    auth_type: AuthType
    token_type: Literal["bearer"] = "bearer"

    @classmethod
    def from_dto(cls, login_info: TokenInfoDTO) -> "TokenResponse":
        return TokenResponse(
            access_token=login_info.access_token,
            refresh_token=login_info.refresh_token,
            auth_type=login_info.auth_type,
        )
