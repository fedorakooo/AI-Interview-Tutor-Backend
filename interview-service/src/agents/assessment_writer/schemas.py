from pydantic import BaseModel, Field


class FocusTextSchema(BaseModel):
    focus_id: str
    summary_short: str = Field(min_length=1, max_length=200)
    rationale: str = Field(min_length=1, max_length=3000)
    reference_comparison: str | None = Field(default=None, max_length=2000)


class RedFlagDraftSchema(BaseModel):
    flag: str
    quotes: list[str] = Field(min_length=1)
    reasoning: str = Field(min_length=1)


class AssessmentTextsSchema(BaseModel):
    overall_summary: str = Field(min_length=1, max_length=3000)
    focus: list[FocusTextSchema] = Field(default_factory=list)
    red_flags: list[RedFlagDraftSchema] = Field(default_factory=list)
