"""Per-user daily LLM cost/budget counters (Redis-backed when available)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


class CostBudgetGuard:
    def __init__(self, redis_client=None, daily_limit_usd: float = 5.0) -> None:
        self._redis = redis_client
        self._daily_limit_usd = daily_limit_usd
        self._memory: dict[str, float] = {}

    def _key(self, user_id: str) -> str:
        day = datetime.now(UTC).strftime("%Y%m%d")
        return f"llm-budget:{user_id}:{day}"

    async def add_cost(self, user_id: str, usd: float) -> float:
        key = self._key(user_id)
        if self._redis is None:
            self._memory[key] = self._memory.get(key, 0.0) + usd
            return self._memory[key]
        try:
            value = await self._redis.incrbyfloat(key, usd)
            await self._redis.expire(key, 60 * 60 * 36)
            return float(value)
        except Exception:
            logger.exception("Failed updating cost budget for %s", user_id)
            return 0.0

    async def allowed(self, user_id: str) -> bool:
        key = self._key(user_id)
        if self._redis is None:
            return self._memory.get(key, 0.0) < self._daily_limit_usd
        try:
            raw = await self._redis.get(key)
            current = float(raw or 0)
            return current < self._daily_limit_usd
        except Exception:
            return True
