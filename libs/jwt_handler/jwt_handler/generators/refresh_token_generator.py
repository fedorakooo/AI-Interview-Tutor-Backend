from jwt_handler.config import settings
from jwt_handler.interfaces import IRefreshTokenGenerator, ITokenHandler
from jwt_handler.value_objects import RefreshTokenPayload, TokenType


class RefreshTokenGenerator(IRefreshTokenGenerator):
    def __init__(
        self,
        token_handler: ITokenHandler,
    ):
        self.token_handler = token_handler
        self.expire_minutes = settings.refresh_token_expire_minutes

    def generate_refresh_token(self, user_id: str, username: str, auth_version: int = 0) -> str:
        payload = RefreshTokenPayload(
            id=user_id,
            username=username,
            type=TokenType.REFRESH,
            auth_version=auth_version,
        )
        return self.token_handler.encode_jwt(
            payload=payload,
            expire_minutes=self.expire_minutes,
        )
