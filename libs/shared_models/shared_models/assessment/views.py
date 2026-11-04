from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, computed_field, model_validator

from shared_models.assessment.contracts import CvPolicy
from shared_models.assessment.evidence import EvidenceLevel, Verdict


class QuoteView(BaseModel):
    event_seq: int = Field(ge=1)
    start: int = Field(ge=0)
    end: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def span_matches_text(self) -> "QuoteView":
        if self.end <= self.start:
            raise ValueError("Quote end must be greater than start")
        if len(self.text) != self.end - self.start:
            raise ValueError("Quote text length must match the span")
        return self


class EvidenceView(BaseModel):
    evidence_id: UUID
    focus_id: str = Field(min_length=1, max_length=64)
    question_seq: int = Field(ge=1)
    answer_seq: int = Field(ge=1)
    level: EvidenceLevel
    matched_signals: list[str] = Field(default_factory=list, max_length=10)
    quotes: list[QuoteView] = Field(min_length=1, max_length=5)
    reasoning: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def answer_follows_question(self) -> "EvidenceView":
        if self.answer_seq <= self.question_seq:
            raise ValueError("answer_seq must come after question_seq")
        return self


class ReviewEntryView(BaseModel):
    review_id: UUID
    author_id: UUID
    created_at: datetime
    comment: str = Field(min_length=1, max_length=2000)
    manual_verdict: Verdict | None = None


class FocusAssessmentView(BaseModel):
    focus_id: str = Field(min_length=1, max_length=64)
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    summary_short: str = Field(min_length=1, max_length=200)
    rationale: str = Field(min_length=1, max_length=3000)
    evidence: list[EvidenceView] = Field(default_factory=list)
    covered_must_cover: list[str] = Field(default_factory=list)
    missed_must_cover: list[str] = Field(default_factory=list)
    reference_comparison: str | None = Field(default=None, max_length=2000)
    review: list[ReviewEntryView] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def final_verdict(self) -> Verdict:
        for entry in reversed(self.review):
            if entry.manual_verdict is not None:
                return entry.manual_verdict
        return self.verdict


class AssessmentCoverageView(BaseModel):
    focus_total: int = Field(ge=1)
    focus_assessed: int = Field(ge=0)
    required_total: int = Field(ge=1)
    required_assessed: int = Field(ge=0)
    questions_asked: int = Field(ge=0)


class FocusOverview(BaseModel):
    focus_id: str
    skill: str
    required: bool
    weight: int
    verdict: Verdict
    final_verdict: Verdict
    confidence: float
    summary_short: str
    evidence_count: int
    matched_strong_signals: list[str] = Field(default_factory=list)
    matched_weak_signals: list[str] = Field(default_factory=list)
    covered_must_cover: list[str] = Field(default_factory=list)
    missed_must_cover: list[str] = Field(default_factory=list)
    reviewed: bool


class RedFlagOverview(BaseModel):
    flag: str
    reasoning: str


class AssessmentOverview(BaseModel):
    assessment_id: UUID
    attempt_id: UUID
    template_version: int
    report_version: int
    generator_version: str
    generated_at: datetime
    coverage: AssessmentCoverageView
    overall_summary: str
    focus: list[FocusOverview]
    red_flags: list[RedFlagOverview]


class TimelineEntry(BaseModel):
    question_seq: int
    question_text: str
    answer_seq: int
    answer_text: str
    custom_question: bool
    evidence: EvidenceView | None = None


class FocusDetail(BaseModel):
    focus: FocusAssessmentView
    skill: str
    required: bool
    weight: int
    expected_level: str
    reference_answer: str | None = None
    timeline: list[TimelineEntry]


class ReviewRequest(BaseModel):
    author_id: UUID
    comment: str = Field(min_length=1, max_length=2000)
    manual_verdict: Verdict | None = None


class TemplateDraftRequest(BaseModel):
    brief: str = Field(min_length=1, max_length=8000)
    job_description: str | None = Field(default=None, max_length=20000)
    title: str | None = Field(default=None, max_length=200)
    seniority: str | None = Field(default=None, max_length=64)
    language: str = Field(default="en", pattern=r"^[a-z]{2,3}(-[A-Za-z]{2,4})?$")
    cv_policy: CvPolicy = CvPolicy.REQUIRED
    candidate_feedback: bool = False


class FeedbackView(BaseModel):
    attempt_id: UUID
    version: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=4000)
    source: Literal["generated", "edited"]
    editor_id: UUID | None = None
    created_at: datetime


class FeedbackEditRequest(BaseModel):
    editor_id: UUID
    text: str = Field(min_length=1, max_length=4000)


class ErasureRequest(BaseModel):
    cv_correlation_id: UUID | None = None


class ErasureResult(BaseModel):
    attempt_id: UUID
    deleted: dict[str, int]
