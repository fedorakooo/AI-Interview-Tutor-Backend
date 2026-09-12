import pytest
from jwt_handler.handlers.token_handler import JWTTokenHandler
from jwt_handler.exceptions import ExpiredSignatureError, InvalidTokenError


@pytest.fixture
def rsa_keys(tmp_path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

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


def test_encode_decode_roundtrip(rsa_keys):
    private_pem, public_pem = rsa_keys
    handler = JWTTokenHandler(public_key=public_pem, private_key=private_pem)
    token = handler.encode_jwt({"id": "1", "username": "alice", "type": "ACCESS"}, expire_minutes=5)
    payload = handler.decode_jwt(token)
    assert payload["username"] == "alice"
    assert payload["id"] == "1"


def test_expired_token_raises(rsa_keys):
    private_pem, public_pem = rsa_keys
    handler = JWTTokenHandler(public_key=public_pem, private_key=private_pem)
    token = handler.encode_jwt({"id": "1", "username": "alice", "type": "ACCESS"}, expire_minutes=-1)
    with pytest.raises((ExpiredSignatureError, InvalidTokenError)):
        handler.decode_jwt(token)


def test_invalid_token_raises(rsa_keys):
    _, public_pem = rsa_keys
    handler = JWTTokenHandler(public_key=public_pem, private_key="")
    with pytest.raises(InvalidTokenError):
        handler.decode_jwt("not-a-jwt")


def test_access_token_generator_produces_token(rsa_keys):
    from jwt_handler.generators.access_token_generator import AccessTokenGenerator

    private_pem, public_pem = rsa_keys
    handler = JWTTokenHandler(public_key=public_pem, private_key=private_pem)
    generator = AccessTokenGenerator(token_handler=handler)
    token = generator.generate_access_token(
        user_id="user-1",
        username="alice",
        user_role="USER",
        is_blocked=False,
    )
    payload = handler.decode_jwt(token)
    assert payload["username"] == "alice"
    assert payload["id"] == "user-1"


def test_refresh_token_generator_produces_refresh_type(rsa_keys):
    from jwt_handler.generators.refresh_token_generator import RefreshTokenGenerator
    from jwt_handler.value_objects import TokenType

    private_pem, public_pem = rsa_keys
    handler = JWTTokenHandler(public_key=public_pem, private_key=private_pem)
    generator = RefreshTokenGenerator(token_handler=handler)
    token = generator.generate_refresh_token(user_id="user-1", username="alice")
    payload = handler.decode_jwt(token)
    assert payload["type"] == TokenType.REFRESH
