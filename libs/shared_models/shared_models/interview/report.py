from pydantic import BaseModel, Field


class SkillScore(BaseModel):
    skill: str
    score: float = Field(ge=0, le=10)
    notes: str = ""


class InterviewReport(BaseModel):
    summary: str
    skill_scores: list[SkillScore] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
