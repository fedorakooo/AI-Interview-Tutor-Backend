from uuid import UUID

from pydantic import BaseModel, Field, model_validator
from shared_models.assessment.evidence import EvidenceLevel


class QuoteDocument(BaseModel):
    event_seq: int = Field(ge=1)
    start: int = Field(ge=0)
    end: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def span_matches_text(self) -> "QuoteDocument":
        if self.end <= self.start:
            raise ValueError("Quote end must be greater than start")
        if len(self.text) != self.end - self.start:
            raise ValueError("Quote text length must match the span")
        return self


class EvidenceDocument(BaseModel):
    evidence_id: UUID
    focus_id: str = Field(min_length=1, max_length=64)
    question_seq: int = Field(ge=1)
    answer_seq: int = Field(ge=1)
    level: EvidenceLevel
    matched_signals: list[str] = Field(default_factory=list, max_length=10)
    quotes: list[QuoteDocument] = Field(min_length=1, max_length=5)
    reasoning: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def answer_follows_question(self) -> "EvidenceDocument":
        if self.answer_seq <= self.question_seq:
            raise ValueError("answer_seq must come after question_seq")
        return self
