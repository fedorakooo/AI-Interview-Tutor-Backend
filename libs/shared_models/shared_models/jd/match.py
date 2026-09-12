from __future__ import annotations

from pydantic import BaseModel, Field


class JDRequirement(BaseModel):
    skill: str
    importance: str = "nice_to_have"  # required | nice_to_have
    evidence: str = ""


class JDMatchResult(BaseModel):
    match_score: float = Field(ge=0, le=100)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    requirements: list[JDRequirement] = Field(default_factory=list)
    summary: str = ""


class JDMatchRequest(BaseModel):
    job_description: str = Field(min_length=40)
    cv_correlation_id: str | None = None
