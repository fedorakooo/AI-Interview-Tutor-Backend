import pytest
from fastapi import HTTPException
from src.api.dependencies.internal import require_internal_service
from src.config import settings


@pytest.fixture(autouse=True)
def configured_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings.assessment_settings, "internal_service_token", "internal-secret")


@pytest.mark.asyncio
async def test_the_configured_token_is_accepted():
    assert await require_internal_service("internal-secret") is None


@pytest.mark.asyncio
@pytest.mark.parametrize("token", [None, "", "wrong", "tökén"])
async def test_other_tokens_get_401_even_when_they_are_not_ascii(token):
    with pytest.raises(HTTPException) as error:
        await require_internal_service(token)

    assert error.value.status_code == 401
