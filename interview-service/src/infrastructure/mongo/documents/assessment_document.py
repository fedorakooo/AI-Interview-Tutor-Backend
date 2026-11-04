from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, computed_field
from shared_models.assessment.evidence import Verdict

from src.infrastructure.mongo.documents.evidence_document import EvidenceDocument, QuoteDocument


class ReviewEntryDocument(BaseModel):
    review_id: UUID
    author_id: UUID
    created_at: datetime
    comment: str = Field(min_length=1, max_length=2000)
    manual_verdict: Verdict | None = None


class FocusAssessmentDocument(BaseModel):
    focus_id: str = Field(min_length=1, max_length=64)
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    summary_short: str = Field(min_length=1, max_length=200)
    rationale: str = Field(min_length=1, max_length=3000)
    evidence: list[EvidenceDocument] = Field(default_factory=list)
    covered_must_cover: list[str] = Field(default_factory=list)
    missed_must_cover: list[str] = Field(default_factory=list)
    reference_comparison: str | None = Field(default=None, max_length=2000)
    review: list[ReviewEntryDocument] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def final_verdict(self) -> Verdict:
        for entry in reversed(self.review):
            if entry.manual_verdict is not None:
                return entry.manual_verdict
        return self.verdict


class RedFlagFindingDocument(BaseModel):
    flag: str = Field(min_length=1, max_length=300)
    quotes: list[QuoteDocument] = Field(min_length=1, max_length=5)
    reasoning: str = Field(min_length=1, max_length=1000)


class AssessmentCoverageDocument(BaseModel):
    focus_total: int = Field(ge=1)
    focus_assessed: int = Field(ge=0)
    required_total: int = Field(ge=1)
    required_assessed: int = Field(ge=0)
    questions_asked: int = Field(ge=0)


class AssessmentDocument(BaseModel):
    assessment_id: UUID
    attempt_id: UUID
    session_id: str = Field(min_length=1, max_length=128)
    template_version: int = Field(ge=1)
    report_version: int = Field(default=1, ge=1)
    generator_version: str = Field(min_length=1, max_length=64)
    generated_at: datetime
    coverage: AssessmentCoverageDocument
    overall_summary: str = Field(min_length=1, max_length=3000)
    focus: list[FocusAssessmentDocument] = Field(min_length=1)
    red_flags: list[RedFlagFindingDocument] = Field(default_factory=list)
