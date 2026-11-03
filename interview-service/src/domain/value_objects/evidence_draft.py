from dataclasses import dataclass

from src.domain.enums.evidence_level import EvidenceLevel


@dataclass(frozen=True)
class EvidenceDraft:
    focus_id: str
    level: EvidenceLevel
    quotes: tuple[str, ...]
    reasoning: str
    matched_signals: tuple[str, ...] = ()
