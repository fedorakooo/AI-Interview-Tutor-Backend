from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class MessageDelta:
    turn_id: UUID
    message_id: UUID
    delta: str
