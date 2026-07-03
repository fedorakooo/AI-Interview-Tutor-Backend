from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from src.domain.entities.user_cv_upload import UserCVUpload


class CVUploadAcceptedResponse(BaseModel):
    correlation_id: UUID
    status: str
    message: str = "CV upload accepted for analysis"


class CVStatusResponse(BaseModel):
    correlation_id: UUID
    status: str
    original_filename: str | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, upload: UserCVUpload) -> "CVStatusResponse":
        return cls(
            correlation_id=upload.correlation_id,
            status=upload.status.value,
            original_filename=upload.original_filename,
            error_code=upload.error_code,
            error_message=upload.error_message,
            created_at=upload.created_at or datetime.min,
            updated_at=upload.updated_at or datetime.min,
        )
