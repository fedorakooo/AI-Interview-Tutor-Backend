from jwt_handler.config import settings
from jwt_handler.interfaces import IAccessTokenGenerator, ITokenHandler
from jwt_handler.value_objects import AccessTokenPayload, TokenType


class AccessTokenGenerator(IAccessTokenGenerator):
    def __init__(
        self,
        token_handler: ITokenHandler,
    ):
        self.token_handler = token_handler
        self.expire_minutes = settings.access_token_expire_minutes

    def generate_access_token(
        self, user_id: str, username: str, user_role: str, is_blocked: bool, auth_version: int = 0
    ) -> str:
        payload = AccessTokenPayload(
            id=user_id,
            username=username,
            role=user_role,
            is_blocked=is_blocked,
            type=TokenType.ACCESS,
            auth_version=auth_version,
        )
        return self.token_handler.encode_jwt(
            payload=payload,
            expire_minutes=self.expire_minutes,
        )
