from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from jwt_handler.config import settings
from jwt_handler.exceptions import ExpiredSignatureError as CustomExpiredSignatureError
from jwt_handler.exceptions import InvalidTokenError as CustomInvalidTokenError
from jwt_handler.interfaces import ITokenHandler
from jwt_handler.value_objects import AccessTokenPayload, RefreshTokenPayload


class JWTTokenHandler(ITokenHandler):
    """Handles JWT token encoding and decoding operations."""

    def __init__(self, public_key: str, private_key: str):
        """Initialize the JWT token handler."""
        self.public_key = public_key
        self.private_key = private_key
        self.algorithm = settings.algorithm

    def encode_jwt(
        self,
        payload: AccessTokenPayload | RefreshTokenPayload,
        expire_minutes: float,
    ) -> str:
        """
        Encode a JWT token with the given payload and expiration time.

        Args:
            payload: Token payload data
            expire_minutes: Token expiration time in minutes

        Returns:
            Encoded JWT token string
        """
        now = datetime.now(UTC)
        expire = now + timedelta(minutes=expire_minutes)

        to_encode = {
            **payload,
            "jti": uuid4().hex,
            "exp": expire,
            "iat": now,
        }

        encoded = jwt.encode(
            payload=to_encode,
            key=self.private_key,
            algorithm=self.algorithm,
        )
        return encoded

    def decode_jwt(
        self,
        token: str | bytes,
    ) -> AccessTokenPayload | RefreshTokenPayload:
        """
        Decode and verify a JWT token.

        Args:
            token: JWT token to decode

        Returns:
            Decoded token payload

        Raises:
            CustomExpiredSignatureError: When token has expired
            CustomInvalidTokenError: When token is invalid
        """
        try:
            decoded = jwt.decode(
                jwt=token,
                key=self.public_key,
                algorithms=[self.algorithm],
                options={"verify_signature": True, "require": ["exp", "iat"]},
            )
        except ExpiredSignatureError as exc:
            raise CustomExpiredSignatureError from exc
        except InvalidTokenError as exc:
            raise CustomInvalidTokenError from exc
        return decoded
