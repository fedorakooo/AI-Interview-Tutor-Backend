from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


class RealtimeBus:
    def __init__(self, redis_client=None, channel_prefix: str = "interview:session:") -> None:
        self._redis = redis_client
        self._prefix = channel_prefix

    async def publish(self, session_id: str, payload: str) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.publish(f"{self._prefix}{session_id}", payload)
        except Exception:
            logger.exception("RealtimeBus publish failed for %s", session_id)

    async def subscribe(self, session_id: str, handler: Callable[[str], Awaitable[None]]) -> None:
        if self._redis is None:
            return
        logger.info("RealtimeBus subscribe stub for session %s (wire redis.pubsub in deploy)", session_id)
