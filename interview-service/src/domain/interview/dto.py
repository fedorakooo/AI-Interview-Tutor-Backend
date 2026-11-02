from dataclasses import dataclass, field

from pydantic import BaseModel, Field
from shared_models.assessment import AssessmentTemplateSnapshot, CustomQuestion, EvidenceLevel, FocusArea
from shared_models.assessment.session_state import FocusCoverage, MessageRecord
from shared_models.cv.cv_data import CVData

from src.domain.interview.engine import AskFocus, AskIntro, Complete


class EvidenceDraft(BaseModel):
    focus_id: str
    level: EvidenceLevel
    matched_signals: list[str] = Field(default_factory=list)
    quotes: list[str] = Field(min_length=1)
    reasoning: str = Field(min_length=1)


class EvaluationResult(BaseModel):
    answer_was_complete: bool
    evidence: list[EvidenceDraft] = Field(default_factory=list)
    covered_must_cover: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class EvaluationRequest:
    template: AssessmentTemplateSnapshot
    target_focus: FocusArea
    question_text: str
    answer_text: str


@dataclass(frozen=True)
class InterviewerRequest:
    template: AssessmentTemplateSnapshot
    action: AskIntro | AskFocus | Complete
    focus: FocusArea | None = None
    custom_question: CustomQuestion | None = None
    coverage: FocusCoverage | None = None
    cv: CVData | None = None
    transcript: list[MessageRecord] = field(default_factory=list)
