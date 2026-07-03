from datetime import datetime
from uuid import UUID

from shared_models.messaging.common import AnalysisStatus


class UserCVUpload:
    def __init__(
        self,
        id: UUID,
        user_id: UUID,
        correlation_id: UUID,
        s3_object_key: str,
        status: AnalysisStatus,
        original_filename: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        mongo_document_id: str | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ):
        self.id = id
        self.user_id = user_id
        self.correlation_id = correlation_id
        self.s3_object_key = s3_object_key
        self.status = status
        self.original_filename = original_filename
        self.error_code = error_code
        self.error_message = error_message
        self.mongo_document_id = mongo_document_id
        self.created_at = created_at
        self.updated_at = updated_at
