from shared_models.assessment import evidence as contract_evidence
from shared_models.assessment import report as contract

from src.domain.entities.review_entry import ReviewEntry
from src.domain.enums.verdict import Verdict


class ReviewEntryMapper:
    @staticmethod
    def to_contract(entry: ReviewEntry) -> contract.ReviewEntry:
        return contract.ReviewEntry(
            review_id=entry.review_id,
            author_id=entry.author_id,
            created_at=entry.created_at,
            comment=entry.comment,
            manual_verdict=contract_evidence.Verdict(entry.manual_verdict.value) if entry.manual_verdict else None,
        )

    @staticmethod
    def to_domain(entry: contract.ReviewEntry) -> ReviewEntry:
        return ReviewEntry(
            review_id=entry.review_id,
            author_id=entry.author_id,
            created_at=entry.created_at,
            comment=entry.comment,
            manual_verdict=Verdict(entry.manual_verdict.value) if entry.manual_verdict else None,
        )
