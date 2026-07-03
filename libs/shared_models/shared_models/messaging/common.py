from enum import StrEnum

from pydantic import BaseModel, Field


class AnalysisStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ExtractionMetadata(BaseModel):
    method: str = Field(description="PDF extraction backend, e.g. docling.")
    page_count: int = Field(ge=0)
    char_count: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)
