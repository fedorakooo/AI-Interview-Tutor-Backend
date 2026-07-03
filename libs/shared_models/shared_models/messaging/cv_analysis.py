from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from shared_models.cv.cv_data import CVData
from shared_models.messaging.common import AnalysisStatus, ExtractionMetadata


class CVAnalysisJobMessage(BaseModel):
    """Inbound RabbitMQ job published when a CV upload is accepted."""

    model_config = ConfigDict(str_strip_whitespace=True)

    correlation_id: UUID = Field(description="Idempotency key for a single CV upload attempt.")
    user_id: UUID
    s3_object_key: str = Field(min_length=1, max_length=512, description="S3 object key for the uploaded PDF.")
    original_filename: str | None = Field(default=None, max_length=255)
    published_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        payload = dict(data)

        if "s3_object_key" not in payload and "url" in payload:
            payload["s3_object_key"] = payload.pop("url")

        if "correlation_id" not in payload:
            payload["correlation_id"] = str(uuid4())

        payload.pop("subject", None)
        payload.pop("body", None)
        return payload

    @field_validator("published_at", mode="before")
    @classmethod
    def _parse_published_at(cls, value: datetime | str) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        return datetime.fromisoformat(value)


class CVAnalysisResultMessage(BaseModel):
    """Outbound RabbitMQ event published after CV analysis finishes."""

    model_config = ConfigDict(str_strip_whitespace=True)

    correlation_id: UUID
    user_id: UUID
    s3_object_key: str = Field(min_length=1, max_length=512)
    status: AnalysisStatus
    mongo_document_id: str | None = None
    error_code: str | None = Field(default=None, max_length=64)
    error_message: str | None = Field(default=None, max_length=512)
    extraction_metadata: ExtractionMetadata | None = None
    published_at: datetime

    @field_validator("published_at", mode="before")
    @classmethod
    def _parse_published_at(cls, value: datetime | str) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        return datetime.fromisoformat(value)


class CVAnalysisDocument(BaseModel):
    """MongoDB persistence envelope for analyzed CV content."""

    correlation_id: UUID
    user_id: UUID
    s3_object_key: str
    status: AnalysisStatus = AnalysisStatus.COMPLETED
    published_at: datetime
    analyzed_at: datetime
    extraction_metadata: ExtractionMetadata | None = None
    cv: CVData

    def to_mongo_dict(self) -> dict[str, Any]:
        document = {
            **self.cv.model_dump(mode="json"),
            "correlation_id": str(self.correlation_id),
            "user_id": str(self.user_id),
            "s3_object_key": self.s3_object_key,
            "source_url": self.s3_object_key,
            "status": self.status.value,
            "published_at": self.published_at.isoformat(),
            "analyzed_at": self.analyzed_at.isoformat(),
        }
        if self.extraction_metadata is not None:
            document["extraction_metadata"] = self.extraction_metadata.model_dump(mode="json")
        return document


# Backward-compatible aliases for existing imports and docs.
CVInitialAnalysisMessage = CVAnalysisJobMessage
CVResultAnalysisMessage = CVAnalysisResultMessage
