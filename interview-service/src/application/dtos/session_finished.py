from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class SessionFinished:
    event_id: UUID
    seq: int
