from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from jwt_handler.value_objects import CANDIDATE_INTERVIEW_AUDIENCE, TokenType, candidate_interview_scope

from tests.conftest import PRIVATE_KEY


def mint_interview_token(attempt_id: UUID, **overrides: object) -> str:
    now = datetime.now(UTC)
    claims: dict[str, object] = {
        "sub": str(attempt_id),
        "aud": CANDIDATE_INTERVIEW_AUDIENCE,
        "scope": candidate_interview_scope(str(attempt_id)),
        "jti": uuid4().hex,
        "type": TokenType.CANDIDATE_INTERVIEW,
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    claims.update(overrides)
    return jwt.encode(claims, PRIVATE_KEY, algorithm="RS256")
