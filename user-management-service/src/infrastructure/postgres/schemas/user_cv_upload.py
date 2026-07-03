from datetime import datetime
from uuid import UUID

from shared_models.messaging.common import AnalysisStatus
from sqlalchemy import ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.user_cv_upload import UserCVUpload
from src.infrastructure.postgres.database import Base


class UserCVUploadORM(Base):
    __tablename__ = "user_cv_uploads"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    correlation_id: Mapped[UUID] = mapped_column(unique=True)
    s3_object_key: Mapped[str] = mapped_column(String(512))
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32))
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    mongo_document_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("TIMEZONE('utc', now())"))
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("TIMEZONE('utc', now())"),
        onupdate=text("TIMEZONE('utc', now())"),
    )

    def to_entity(self) -> UserCVUpload:
        return UserCVUpload(
            id=self.id,
            user_id=self.user_id,
            correlation_id=self.correlation_id,
            s3_object_key=self.s3_object_key,
            status=AnalysisStatus(self.status),
            original_filename=self.original_filename,
            error_code=self.error_code,
            error_message=self.error_message,
            mongo_document_id=self.mongo_document_id,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, entity: UserCVUpload) -> "UserCVUploadORM":
        return UserCVUploadORM(
            id=entity.id,
            user_id=entity.user_id,
            correlation_id=entity.correlation_id,
            s3_object_key=entity.s3_object_key,
            original_filename=entity.original_filename,
            status=entity.status.value,
            error_code=entity.error_code,
            error_message=entity.error_message,
            mongo_document_id=entity.mongo_document_id,
        )
