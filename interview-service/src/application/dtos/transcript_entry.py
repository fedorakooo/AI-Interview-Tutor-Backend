from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID


@dataclass(frozen=True)
class TranscriptEntry:
    event_id: UUID
    seq: int
    role: Literal["interviewer", "candidate"]
    text: str
    occurred_at: datetime
