from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID


@dataclass(frozen=True)
class FeedbackEntry:
    attempt_id: UUID
    version: int
    text: str
    source: Literal["generated", "edited"]
    created_at: datetime
    editor_id: UUID | None = None
