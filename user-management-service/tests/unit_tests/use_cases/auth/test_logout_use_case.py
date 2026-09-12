from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from jwt_handler.exceptions import InvalidTokenError
from jwt_handler.value_objects import TokenType

from src.application.use_cases.auth.logout_use_case import LogoutUseCase


@pytest.fixture
def mock_token_handler():
    return MagicMock()


@pytest.fixture
def mock_redis():
    return AsyncMock()


@pytest.mark.asyncio
async def test_logout_blacklists_refresh_token(mock_token_handler, mock_redis):
    exp = datetime.now().timestamp() + 3600
    mock_token_handler.decode_jwt.return_value = {"type": TokenType.REFRESH, "exp": exp}

    use_case = LogoutUseCase(redis_client=mock_redis, token_handler=mock_token_handler)
    await use_case("refresh-token-value")

    mock_redis.setex.assert_awaited_once()
    args, kwargs = mock_redis.setex.await_args
    assert kwargs["key"] == "refresh-key:refresh-token-value"
    assert kwargs["value"] == "refresh-token-value"
    assert kwargs["time"] > 0


@pytest.mark.asyncio
async def test_logout_rejects_non_refresh_token(mock_token_handler, mock_redis):
    mock_token_handler.decode_jwt.return_value = {"type": TokenType.ACCESS, "exp": datetime.now().timestamp() + 60}

    use_case = LogoutUseCase(redis_client=mock_redis, token_handler=mock_token_handler)
    with pytest.raises(InvalidTokenError):
        await use_case("bad-token")
    mock_redis.setex.assert_not_awaited()


@pytest.mark.asyncio
async def test_logout_skips_expired_token(mock_token_handler, mock_redis):
    mock_token_handler.decode_jwt.return_value = {"type": TokenType.REFRESH, "exp": datetime.now().timestamp() - 10}

    use_case = LogoutUseCase(redis_client=mock_redis, token_handler=mock_token_handler)
    await use_case("expired-token")
    mock_redis.setex.assert_not_awaited()
