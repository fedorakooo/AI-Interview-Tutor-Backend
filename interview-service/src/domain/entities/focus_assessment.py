from dataclasses import dataclass

from src.domain.entities.review_entry import ReviewEntry
from src.domain.enums.verdict import Verdict
from src.domain.value_objects.evidence_item import EvidenceItem


@dataclass(frozen=True)
class FocusAssessment:
    focus_id: str
    verdict: Verdict
    confidence: float
    summary_short: str
    rationale: str
    evidence: tuple[EvidenceItem, ...] = ()
    covered_must_cover: tuple[str, ...] = ()
    missed_must_cover: tuple[str, ...] = ()
    reference_comparison: str | None = None
    review: tuple[ReviewEntry, ...] = ()

    @property
    def final_verdict(self) -> Verdict:
        for entry in reversed(self.review):
            if entry.manual_verdict is not None:
                return entry.manual_verdict
        return self.verdict
