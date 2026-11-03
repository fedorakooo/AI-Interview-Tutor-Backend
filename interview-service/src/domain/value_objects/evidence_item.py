from dataclasses import dataclass
from uuid import UUID

from src.domain.enums.evidence_level import EvidenceLevel
from src.domain.exceptions.invalid_value_errors import InvalidDomainValueError
from src.domain.value_objects.quote_ref import QuoteRef


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: UUID
    focus_id: str
    question_seq: int
    answer_seq: int
    level: EvidenceLevel
    matched_signals: tuple[str, ...]
    quotes: tuple[QuoteRef, ...]
    reasoning: str

    def __post_init__(self) -> None:
        if self.answer_seq <= self.question_seq:
            raise InvalidDomainValueError("answer_seq must come after question_seq")
        if not self.quotes:
            raise InvalidDomainValueError("Evidence needs at least one quote")
