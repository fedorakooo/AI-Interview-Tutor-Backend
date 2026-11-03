from pydantic import BaseModel, Field
from shared_models.assessment import AssessmentMode, FocusMethod


class DraftFocus(BaseModel):
    skill: str
    what_to_learn: str = ""
    required: bool = False
    weight: int = 1
    expected_level: str = "middle"
    guidance: str = ""
    method: FocusMethod = FocusMethod.QUESTIONS
    strong_signals: list[str] = Field(default_factory=list)
    weak_signals: list[str] = Field(default_factory=list)
    must_cover: list[str] = Field(default_factory=list)
    min_evidence: int = 2
    max_questions: int = 3


class DraftCustomQuestion(BaseModel):
    focus_skill: str
    text: str
    reference_answer: str | None = None
    required: bool = False


class SpecDraft(BaseModel):
    mode: AssessmentMode = AssessmentMode.MIXED
    question_count: int = 10
    duration_minutes: int = 45
    focus_areas: list[DraftFocus] = Field(default_factory=list)
    skip: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    custom_questions: list[DraftCustomQuestion] = Field(default_factory=list)
