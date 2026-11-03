from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.domain.enums.verdict import Verdict


@dataclass(frozen=True)
class ReviewEntry:
    review_id: UUID
    author_id: UUID
    created_at: datetime
    comment: str
    manual_verdict: Verdict | None = None
