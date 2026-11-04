from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from shared_models.assessment.contracts import CvPolicy
from shared_models.assessment.evidence import EvidenceItem, Verdict
from shared_models.assessment.report import AssessmentCoverage, FocusAssessment


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
    coverage: AssessmentCoverage
    overall_summary: str
    focus: list[FocusOverview]
    red_flags: list[RedFlagOverview]


class TimelineEntry(BaseModel):
    question_seq: int
    question_text: str
    answer_seq: int
    answer_text: str
    custom_question: bool
    evidence: EvidenceItem | None = None


class FocusDetail(BaseModel):
    focus: FocusAssessment
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
