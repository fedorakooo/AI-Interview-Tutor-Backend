from dataclasses import dataclass

from pydantic import BaseModel, Field
from shared_models.assessment import AssessmentTemplateSnapshot, Verdict
from shared_models.assessment.session_state import SessionState


class FocusText(BaseModel):
    focus_id: str
    summary_short: str = Field(min_length=1, max_length=200)
    rationale: str = Field(min_length=1, max_length=3000)
    reference_comparison: str | None = Field(default=None, max_length=2000)


class RedFlagDraft(BaseModel):
    flag: str
    quotes: list[str] = Field(min_length=1)
    reasoning: str = Field(min_length=1)


class AssessmentTexts(BaseModel):
    overall_summary: str = Field(min_length=1, max_length=3000)
    focus: list[FocusText] = Field(default_factory=list)
    red_flags: list[RedFlagDraft] = Field(default_factory=list)


@dataclass(frozen=True)
class AssessmentDigest:
    template: AssessmentTemplateSnapshot
    state: SessionState
    verdicts: dict[str, tuple[Verdict, float]]
