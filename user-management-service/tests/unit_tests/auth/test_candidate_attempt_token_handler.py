import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt_handler.handlers import CandidateInterviewTokenVerifier
from jwt_handler.value_objects import TokenType
from src.domain.exceptions.candidate_attempt_token_errors import CandidateAttemptTokenError
from src.infrastructure.auth.candidate_attempt_token_handler import CandidateAttemptTokenHandler


@pytest.fixture
def token_handler() -> CandidateAttemptTokenHandler:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_key = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_key = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return CandidateAttemptTokenHandler(public_key=public_key, private_key=private_key)


def test_candidate_attempt_token_has_required_isolated_claims(token_handler):
    token = token_handler.mint("attempt-1")

    payload = token_handler.verify(token, "attempt-1")

    assert payload["sub"] == "attempt-1"
    assert payload["aud"] == "candidate-assessment"
    assert payload["scope"] == "candidate_attempt:attempt-1"
    assert payload["jti"]


def test_candidate_attempt_token_cannot_be_used_for_another_attempt(token_handler):
    token = token_handler.mint("attempt-1")

    with pytest.raises(CandidateAttemptTokenError):
        token_handler.verify(token, "attempt-2")


def test_interview_token_is_verified_by_the_shared_verifier(token_handler):
    token = token_handler.mint_interview_token("attempt-1")

    payload = CandidateInterviewTokenVerifier(token_handler.public_key).verify(token)

    assert payload["sub"] == "attempt-1"
    assert payload["type"] == TokenType.CANDIDATE_INTERVIEW


def test_start_token_cannot_open_an_interview(token_handler):
    token = token_handler.mint("attempt-1")

    with pytest.raises(Exception):
        CandidateInterviewTokenVerifier(token_handler.public_key).verify(token)


def test_interview_token_cannot_be_used_as_attempt_token(token_handler):
    token = token_handler.mint_interview_token("attempt-1")

    with pytest.raises(CandidateAttemptTokenError):
        token_handler.verify(token, "attempt-1")
