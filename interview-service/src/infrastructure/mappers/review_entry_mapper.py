from src.domain.entities.review_entry import ReviewEntry
from src.domain.enums.verdict import Verdict
from src.infrastructure.mongo.documents.assessment_document import ReviewEntryDocument


class ReviewEntryMapper:
    @staticmethod
    def to_model(entry: ReviewEntry) -> ReviewEntryDocument:
        return ReviewEntryDocument(
            review_id=entry.review_id,
            author_id=entry.author_id,
            created_at=entry.created_at,
            comment=entry.comment,
            manual_verdict=entry.manual_verdict.value if entry.manual_verdict else None,
        )

    @staticmethod
    def to_domain(entry: ReviewEntryDocument) -> ReviewEntry:
        return ReviewEntry(
            review_id=entry.review_id,
            author_id=entry.author_id,
            created_at=entry.created_at,
            comment=entry.comment,
            manual_verdict=Verdict(entry.manual_verdict.value) if entry.manual_verdict else None,
        )
