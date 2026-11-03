from pydantic import BaseModel, Field

from src.domain.enums.evidence_level import EvidenceLevel


class EvidenceDraftSchema(BaseModel):
    focus_id: str
    level: EvidenceLevel
    matched_signals: list[str] = Field(default_factory=list)
    quotes: list[str] = Field(min_length=1)
    reasoning: str = Field(min_length=1)


class EvaluationResultSchema(BaseModel):
    answer_was_complete: bool
    evidence: list[EvidenceDraftSchema] = Field(default_factory=list)
    covered_must_cover: list[str] = Field(default_factory=list)
