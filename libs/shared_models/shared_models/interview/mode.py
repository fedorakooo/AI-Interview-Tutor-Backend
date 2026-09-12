from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class InterviewMode(StrEnum):
    BEHAVIORAL = "behavioral"
    TECHNICAL = "technical"
    SYSTEM_DESIGN = "system_design"
    MIXED = "mixed"
    CODING = "coding"


class InterviewStartConfig(BaseModel):
    mode: InterviewMode = InterviewMode.MIXED
    company_preset: str | None = None
    role_track: str | None = None
    job_description: str | None = None
    language: str = "en"
    voice_enabled: bool = False


class TranscriptMessage(BaseModel):
    role: str
    content: str
    timestamp: datetime | None = None
    stage: str | None = None


class InterviewTranscript(BaseModel):
    session_id: str
    user_id: str
    messages: list[TranscriptMessage] = Field(default_factory=list)
