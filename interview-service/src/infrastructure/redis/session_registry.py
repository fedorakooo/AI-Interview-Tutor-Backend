import json
from dataclasses import dataclass
from datetime import UTC, datetime

from redis.asyncio import Redis
from shared_models.interview.session import InterviewSessionStatus
from src.config import settings


@dataclass(frozen=True)
class SessionRegistryEntry:
    session_id: str
    user_id: str
    instance_id: str
    status: InterviewSessionStatus
    started_at: datetime


class RedisSessionRegistry:
    KEY_PREFIX = "interview"

    def __init__(self, redis: Redis, instance_id: str) -> None:
        self._redis = redis
        self._instance_id = instance_id
        self._ttl = settings.redis_settings.session_ttl_seconds

    def _session_key(self, session_id: str) -> str:
        return f"{self.KEY_PREFIX}:session:{session_id}"

    def _user_sessions_key(self, user_id: str) -> str:
        return f"{self.KEY_PREFIX}:user:{user_id}:sessions"

    def _instance_sessions_key(self, instance_id: str | None = None) -> str:
        resolved = instance_id or self._instance_id
        return f"{self.KEY_PREFIX}:instance:{resolved}:sessions"

    async def register_session(
        self,
        session_id: str,
        user_id: str,
        status: InterviewSessionStatus = InterviewSessionStatus.ACTIVE,
    ) -> None:
        payload = {
            "session_id": session_id,
            "user_id": user_id,
            "instance_id": self._instance_id,
            "status": status.value,
            "started_at": datetime.now(UTC).isoformat(),
        }
        session_key = self._session_key(session_id)
        pipe = self._redis.pipeline()
        pipe.set(session_key, json.dumps(payload), ex=self._ttl)
        pipe.sadd(self._user_sessions_key(user_id), session_id)
        pipe.sadd(self._instance_sessions_key(), session_id)
        await pipe.execute()

    async def refresh_session(self, session_id: str) -> None:
        session_key = self._session_key(session_id)
        await self._redis.expire(session_key, self._ttl)

    async def update_status(self, session_id: str, status: InterviewSessionStatus) -> None:
        session_key = self._session_key(session_id)
        raw = await self._redis.get(session_key)
        if not raw:
            return
        payload = json.loads(raw)
        payload["status"] = status.value
        await self._redis.set(session_key, json.dumps(payload), ex=self._ttl)

    async def unregister_session(self, session_id: str, user_id: str) -> None:
        pipe = self._redis.pipeline()
        pipe.delete(self._session_key(session_id))
        pipe.srem(self._user_sessions_key(user_id), session_id)
        pipe.srem(self._instance_sessions_key(), session_id)
        await pipe.execute()

    async def get_session(self, session_id: str) -> SessionRegistryEntry | None:
        raw = await self._redis.get(self._session_key(session_id))
        if not raw:
            return None
        payload = json.loads(raw)
        return SessionRegistryEntry(
            session_id=payload["session_id"],
            user_id=payload["user_id"],
            instance_id=payload["instance_id"],
            status=InterviewSessionStatus(payload["status"]),
            started_at=datetime.fromisoformat(payload["started_at"]),
        )

    async def list_instance_sessions(self, instance_id: str | None = None) -> list[str]:
        return list(await self._redis.smembers(self._instance_sessions_key(instance_id)))

    async def ping(self) -> bool:
        return (await self._redis.ping()) is True
