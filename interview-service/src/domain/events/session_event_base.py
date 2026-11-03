from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class SessionEventBase:
    event_id: UUID
    session_id: str
    seq: int
    occurred_at: datetime
