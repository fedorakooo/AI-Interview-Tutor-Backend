import os
from pathlib import Path
from uuid import uuid4

import pytest

_FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


def _fixture_pem(name: str) -> str:
    return (_FIXTURES_DIR / name).read_text()


PUBLIC_KEY = os.environ.get("PUBLIC_KEY", _fixture_pem("dev_rsa_public.pem"))
PRIVATE_KEY = os.environ.get("PRIVATE_KEY", _fixture_pem("dev_rsa_private.pem"))


@pytest.fixture(autouse=True)
def forbid_real_model_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    try:
        from pydantic_ai import models
    except ImportError:
        return
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", False)


@pytest.fixture
def token_handler():
    from jwt_handler.handlers import JWTTokenHandler

    return JWTTokenHandler(public_key=PUBLIC_KEY, private_key=PRIVATE_KEY)


@pytest.fixture
def user_id() -> str:
    return str(uuid4())


@pytest.fixture
def access_token(token_handler, user_id: str) -> str:
    from jwt_handler.value_objects import AccessTokenPayload, TokenType

    payload = AccessTokenPayload(
        id=user_id,
        username="testuser",
        role="USER",
        is_blocked=False,
        type=TokenType.ACCESS,
    )
    return token_handler.encode_jwt(payload=payload, expire_minutes=30)
