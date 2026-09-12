from __future__ import annotations

import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


class CostBudgetTracker:
    def __init__(self, redis_client=None, *, daily_token_cap: int = 250_000) -> None:
        self._redis = redis_client
        self._cap = daily_token_cap

    def _key(self, user_id: str) -> str:
        day = datetime.now(UTC).strftime("%Y%m%d")
        return f"cost_budget:{user_id}:{day}"

    async def get_usage(self, user_id: str) -> int:
        if self._redis is None:
            return 0
        try:
            raw = await self._redis.get(self._key(user_id))
            return int(raw or 0)
        except Exception:
            logger.exception("CostBudgetTracker.get_usage failed")
            return 0

    async def add_tokens(self, user_id: str, tokens: int) -> int:
        if self._redis is None:
            return tokens
        try:
            key = self._key(user_id)
            new_total = await self._redis.incrby(key, tokens)
            await self._redis.expire(key, 86_400)
            return int(new_total)
        except Exception:
            logger.exception("CostBudgetTracker.add_tokens failed")
            return tokens

    async def is_over_budget(self, user_id: str) -> bool:
        return await self.get_usage(user_id) >= self._cap
