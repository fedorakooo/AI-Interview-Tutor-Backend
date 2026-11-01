from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from jwt.exceptions import InvalidTokenError

from src.domain.exceptions.candidate_attempt_token_errors import CandidateAttemptTokenError
from src.domain.interfaces.auth.candidate_attempt_token_handler import (
    CandidateAttemptTokenPayload,
    ICandidateAttemptTokenHandler,
)


class CandidateAttemptTokenHandler(ICandidateAttemptTokenHandler):
    """Issues credentials that cannot be used as employer bearer tokens."""

    audience = "candidate-assessment"

    def __init__(self, public_key: str, private_key: str, expire_minutes: int = 30) -> None:
        self.public_key = public_key
        self.private_key = private_key
        self.expire_minutes = expire_minutes

    def mint(self, attempt_id: str) -> str:
        now = datetime.now(UTC)
        payload: CandidateAttemptTokenPayload = {
            "sub": attempt_id,
            "aud": self.audience,
            "scope": f"candidate_attempt:{attempt_id}",
            "jti": str(uuid4()),
        }
        return jwt.encode(
            {**payload, "iat": now, "exp": now + timedelta(minutes=self.expire_minutes)},
            self.private_key,
            algorithm="RS256",
        )

    def verify(self, token: str, expected_attempt_id: str) -> CandidateAttemptTokenPayload:
        try:
            payload = jwt.decode(
                token,
                self.public_key,
                algorithms=["RS256"],
                audience=self.audience,
                options={"require": ["sub", "aud", "scope", "jti", "exp"]},
            )
        except InvalidTokenError as exc:
            raise CandidateAttemptTokenError("Invalid candidate attempt token") from exc

        if payload["sub"] != expected_attempt_id or payload["scope"] != f"candidate_attempt:{expected_attempt_id}":
            raise CandidateAttemptTokenError("Candidate attempt token is out of scope")
        return payload  # type: ignore[return-value]
