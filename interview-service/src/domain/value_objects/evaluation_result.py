from dataclasses import dataclass

from src.domain.value_objects.evidence_draft import EvidenceDraft


@dataclass(frozen=True)
class EvaluationResult:
    answer_was_complete: bool
    evidence: tuple[EvidenceDraft, ...] = ()
    covered_must_cover: tuple[str, ...] = ()
