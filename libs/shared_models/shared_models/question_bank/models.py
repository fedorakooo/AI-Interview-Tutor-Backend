from __future__ import annotations

from pydantic import BaseModel, Field


class CodingRunRequest(BaseModel):
    language: str = "python"
    source_code: str
    stdin: str = ""
    expected_stdout: str | None = None
    time_limit_ms: int = 3000


class CodingRunResult(BaseModel):
    status: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    passed: bool | None = None
    runtime_ms: int | None = None
    message: str = ""


class QuestionBankItem(BaseModel):
    question_id: str
    title: str
    prompt: str
    category: str
    difficulty: str = "mid"
    skills: list[str] = Field(default_factory=list)
    company_tags: list[str] = Field(default_factory=list)
    interview_mode: str = "technical"


class LearningPath(BaseModel):
    path_id: str
    title: str
    duration_days: int
    focus_skills: list[str] = Field(default_factory=list)
    milestones: list[str] = Field(default_factory=list)
