from datetime import datetime
from uuid import UUID

from shared_models.assessment import ReviewRequest

from src.domain.entities.review_entry import ReviewEntry
from src.domain.enums.verdict import Verdict


class ReviewMapper:
    @staticmethod
    def to_entry(request: ReviewRequest, review_id: UUID, created_at: datetime) -> ReviewEntry:
        return ReviewEntry(
            review_id=review_id,
            author_id=request.author_id,
            created_at=created_at,
            comment=request.comment,
            manual_verdict=Verdict(request.manual_verdict.value) if request.manual_verdict else None,
        )
