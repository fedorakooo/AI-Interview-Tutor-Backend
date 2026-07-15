from datetime import UTC, datetime
from uuid import UUID, uuid4

from shared_models.messaging.common import AnalysisStatus
from shared_models.messaging.cv_analysis import CVAnalysisJobMessage
from src.config import settings
from src.domain.entities.user_cv_upload import UserCVUpload
from src.domain.exceptions.cv_upload_errors import (
    EmptyFileError,
    FileTooLargeError,
    InvalidPDFError,
    PublishFailedError,
    S3UploadFailedError,
    UnsupportedMediaTypeError,
)
from src.domain.interfaces.database.uow import IUnitOfWork
from src.domain.interfaces.rabbitmq.rabbitmq_producer import IRabbitMQProducer
from src.domain.interfaces.storage.s3_client import IS3Client

PDF_MAGIC = b"%PDF-"


class UploadCVUseCase:
    def __init__(
        self,
        uow: IUnitOfWork,
        s3_client: IS3Client,
        cv_analyzer_producer: IRabbitMQProducer,
    ):
        self.uow = uow
        self.s3_client = s3_client
        self.cv_analyzer_producer = cv_analyzer_producer

    async def __call__(
        self,
        user_id: UUID,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> UserCVUpload:
        self._validate_upload(file_bytes, content_type)

        correlation_id = uuid4()
        s3_object_key = f"cvs/{user_id}/{correlation_id}.pdf"

        try:
            await self.s3_client.put_object(
                key=s3_object_key,
                body=file_bytes,
                content_type=content_type,
            )
        except Exception as exc:
            raise S3UploadFailedError(str(exc)) from exc

        upload = UserCVUpload(
            id=uuid4(),
            user_id=user_id,
            correlation_id=correlation_id,
            s3_object_key=s3_object_key,
            status=AnalysisStatus.PENDING,
            original_filename=filename or None,
        )

        async with self.uow:
            created_upload = await self.uow.user_cv_upload_repository.create(upload)

        job = CVAnalysisJobMessage(
            correlation_id=correlation_id,
            user_id=user_id,
            s3_object_key=s3_object_key,
            original_filename=filename or None,
            published_at=datetime.now(UTC),
        )

        try:
            await self.cv_analyzer_producer.send_message(job.model_dump_json())
        except Exception as exc:
            failed_upload = UserCVUpload(
                id=created_upload.id,
                user_id=created_upload.user_id,
                correlation_id=created_upload.correlation_id,
                s3_object_key=created_upload.s3_object_key,
                status=AnalysisStatus.FAILED,
                original_filename=created_upload.original_filename,
                error_code="PUBLISH_FAILED",
                error_message=str(exc),
                created_at=created_upload.created_at,
                updated_at=created_upload.updated_at,
            )
            async with self.uow:
                await self.uow.user_cv_upload_repository.update(failed_upload)
            raise PublishFailedError(str(exc)) from exc

        return created_upload

    def _validate_upload(self, file_bytes: bytes, content_type: str) -> None:
        if content_type != "application/pdf":
            raise UnsupportedMediaTypeError()
        if len(file_bytes) == 0:
            raise EmptyFileError()
        if len(file_bytes) > settings.s3_settings.cv_max_upload_bytes:
            raise FileTooLargeError(settings.s3_settings.cv_max_upload_bytes)
        if not file_bytes[:5].startswith(PDF_MAGIC):
            raise InvalidPDFError()
