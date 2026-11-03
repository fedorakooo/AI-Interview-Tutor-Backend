from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class MessageCompleted:
    turn_id: UUID
    event_id: UUID
    seq: int
    text: str
