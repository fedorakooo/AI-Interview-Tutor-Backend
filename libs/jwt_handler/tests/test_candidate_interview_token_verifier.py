from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt_handler.exceptions import ExpiredSignatureError, InvalidTokenError
from jwt_handler.handlers import CandidateInterviewTokenVerifier, JWTTokenHandler
from jwt_handler.value_objects import (
    CANDIDATE_INTERVIEW_AUDIENCE,
    TokenType,
    candidate_interview_scope,
)

ATTEMPT_ID = "attempt-1"


@pytest.fixture(scope="module")
def rsa_keys() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


def mint(private_key: str, **overrides: object) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": ATTEMPT_ID,
        "aud": CANDIDATE_INTERVIEW_AUDIENCE,
        "scope": candidate_interview_scope(ATTEMPT_ID),
        "jti": "jti-1",
        "type": TokenType.CANDIDATE_INTERVIEW,
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    claims.update(overrides)
    return jwt.encode({k: v for k, v in claims.items() if v is not None}, private_key, algorithm="RS256")


def test_valid_token_returns_claims(rsa_keys: tuple[str, str]) -> None:
    private_key, public_key = rsa_keys

    payload = CandidateInterviewTokenVerifier(public_key).verify(mint(private_key))

    assert payload["sub"] == ATTEMPT_ID
    assert payload["type"] == TokenType.CANDIDATE_INTERVIEW


def test_expired_token_is_rejected(rsa_keys: tuple[str, str]) -> None:
    private_key, public_key = rsa_keys
    token = mint(private_key, exp=datetime.now(UTC) - timedelta(minutes=1))

    with pytest.raises(ExpiredSignatureError):
        CandidateInterviewTokenVerifier(public_key).verify(token)


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "candidate-assessment"},
        {"type": TokenType.ACCESS},
        {"type": None},
        {"scope": "candidate_interview:other"},
        {"jti": None},
    ],
)
def test_token_with_wrong_claims_is_rejected(rsa_keys: tuple[str, str], overrides: dict[str, object]) -> None:
    private_key, public_key = rsa_keys

    with pytest.raises(InvalidTokenError):
        CandidateInterviewTokenVerifier(public_key).verify(mint(private_key, **overrides))


def test_token_signed_with_another_key_is_rejected(rsa_keys: tuple[str, str]) -> None:
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_private = other.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    with pytest.raises(InvalidTokenError):
        CandidateInterviewTokenVerifier(rsa_keys[1]).verify(mint(other_private))


def test_candidate_token_is_not_accepted_as_access_token(rsa_keys: tuple[str, str]) -> None:
    private_key, public_key = rsa_keys

    with pytest.raises(InvalidTokenError):
        JWTTokenHandler(public_key=public_key, private_key="").decode_jwt(mint(private_key))
