import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from jwt_handler.config import settings
from jwt_handler.exceptions import ExpiredSignatureError as CustomExpiredSignatureError
from jwt_handler.exceptions import InvalidTokenError as CustomInvalidTokenError
from jwt_handler.interfaces import ICandidateInterviewTokenVerifier
from jwt_handler.value_objects import (
    CANDIDATE_INTERVIEW_AUDIENCE,
    CandidateInterviewTokenPayload,
    TokenType,
    candidate_interview_scope,
)


class CandidateInterviewTokenVerifier(ICandidateInterviewTokenVerifier):
    def __init__(self, public_key: str) -> None:
        self.public_key = public_key
        self.algorithm = settings.algorithm

    def verify(self, token: str | bytes) -> CandidateInterviewTokenPayload:
        try:
            payload = jwt.decode(
                jwt=token,
                key=self.public_key,
                algorithms=[self.algorithm],
                audience=CANDIDATE_INTERVIEW_AUDIENCE,
                options={"require": ["sub", "aud", "scope", "jti", "type", "exp", "iat"]},
            )
        except ExpiredSignatureError as exc:
            raise CustomExpiredSignatureError from exc
        except InvalidTokenError as exc:
            raise CustomInvalidTokenError from exc

        if payload["type"] != TokenType.CANDIDATE_INTERVIEW or payload["scope"] != candidate_interview_scope(
            payload["sub"]
        ):
            raise CustomInvalidTokenError("Token is not a candidate interview token")
        return payload
