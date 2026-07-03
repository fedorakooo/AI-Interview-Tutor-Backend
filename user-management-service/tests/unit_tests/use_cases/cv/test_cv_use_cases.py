from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from shared_models.messaging.common import AnalysisStatus

from src.application.use_cases.cv.get_cv_status_use_case import GetCVStatusUseCase
from src.application.use_cases.cv.upload_cv_use_case import UploadCVUseCase
from src.domain.entities.user_cv_upload import UserCVUpload
from src.domain.exceptions.cv_upload_errors import EmptyFileError, InvalidPDFError, UnsupportedMediaTypeError
from src.domain.exceptions.not_found_error import NotFoundError


@pytest.mark.asyncio
async def test_upload_cv_use_case_valid_pdf() -> None:
    user_id = uuid4()
    uow = AsyncMock()
    created_upload = UserCVUpload(
        id=uuid4(),
        user_id=user_id,
        correlation_id=uuid4(),
        s3_object_key=f"cvs/{user_id}/resume.pdf",
        status=AnalysisStatus.PENDING,
        original_filename="resume.pdf",
    )
    uow.user_cv_upload_repository.create.return_value = created_upload

    s3_client = AsyncMock()
    producer = AsyncMock()

    use_case = UploadCVUseCase(uow=uow, s3_client=s3_client, cv_analyzer_producer=producer)
    result = await use_case(
        user_id=user_id,
        file_bytes=b"%PDF-1.4\nresume",
        filename="resume.pdf",
        content_type="application/pdf",
    )

    assert result.status == AnalysisStatus.PENDING
    s3_client.put_object.assert_awaited_once()
    producer.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_upload_cv_use_case_rejects_invalid_pdf() -> None:
    use_case = UploadCVUseCase(uow=AsyncMock(), s3_client=AsyncMock(), cv_analyzer_producer=AsyncMock())

    with pytest.raises(InvalidPDFError):
        await use_case(
            user_id=uuid4(),
            file_bytes=b"not-a-pdf",
            filename="resume.pdf",
            content_type="application/pdf",
        )


@pytest.mark.asyncio
async def test_upload_cv_use_case_rejects_empty_file() -> None:
    use_case = UploadCVUseCase(uow=AsyncMock(), s3_client=AsyncMock(), cv_analyzer_producer=AsyncMock())

    with pytest.raises(EmptyFileError):
        await use_case(
            user_id=uuid4(),
            file_bytes=b"",
            filename="resume.pdf",
            content_type="application/pdf",
        )


@pytest.mark.asyncio
async def test_upload_cv_use_case_rejects_non_pdf_content_type() -> None:
    use_case = UploadCVUseCase(uow=AsyncMock(), s3_client=AsyncMock(), cv_analyzer_producer=AsyncMock())

    with pytest.raises(UnsupportedMediaTypeError):
        await use_case(
            user_id=uuid4(),
            file_bytes=b"%PDF-1.4",
            filename="resume.txt",
            content_type="text/plain",
        )


@pytest.mark.asyncio
async def test_get_cv_status_use_case_returns_latest() -> None:
    user_id = uuid4()
    upload = UserCVUpload(
        id=uuid4(),
        user_id=user_id,
        correlation_id=uuid4(),
        s3_object_key="cvs/user/resume.pdf",
        status=AnalysisStatus.COMPLETED,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    uow = AsyncMock()
    uow.user_cv_upload_repository.get_latest_by_user_id.return_value = upload

    result = await GetCVStatusUseCase(uow)(user_id=user_id)
    assert result.status == AnalysisStatus.COMPLETED


@pytest.mark.asyncio
async def test_get_cv_status_use_case_not_found() -> None:
    uow = AsyncMock()
    uow.user_cv_upload_repository.get_latest_by_user_id.return_value = None

    with pytest.raises(NotFoundError):
        await GetCVStatusUseCase(uow)(user_id=uuid4())
