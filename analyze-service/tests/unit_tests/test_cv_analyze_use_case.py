from io import BytesIO
from unittest.mock import AsyncMock, Mock

import pytest
from shared_models.cv.cv_data import CVData
from shared_models.messaging.cv_analysis import CVAnalysisJobMessage

from src.agent.errors.cv_parser import ModelOutputParsingException
from src.domain.errors.cv_analysis import ExtractionQualityError, LLMParseError, LLMRateLimitError, S3DownloadError
from src.domain.models.pdf_extraction_result import PDFExtractionResult
from src.use_cases.cv_analyze_use_case import CVAnalyzeUseCase


@pytest.mark.asyncio
async def test_publishes_failed_result_on_quality_gate(job_message: CVAnalysisJobMessage) -> None:
    s3_client = AsyncMock()
    s3_client.get_file.return_value = BytesIO(b"%PDF-1.4\ncontent")

    pdf_loader = Mock()
    pdf_loader.load_with_metadata.return_value = PDFExtractionResult(
        text="short",
        page_count=1,
        char_count=5,
    )

    cv_analyzer = AsyncMock()
    mongo_repository = AsyncMock()
    rabbitmq_producer = AsyncMock()

    use_case = CVAnalyzeUseCase(
        s3_client=s3_client,
        cv_analyzer=cv_analyzer,
        pdf_loader=pdf_loader,
        mongo_repository=mongo_repository,
        rabbitmq_producer=rabbitmq_producer,
    )

    with pytest.raises(ExtractionQualityError):
        await use_case(job_message.model_dump(mode="json"))

    rabbitmq_producer.send_message.assert_awaited_once()
    payload = rabbitmq_producer.send_message.await_args.args[0]
    assert '"status":"failed"' in payload
    assert "EXTRACTION_EMPTY" in payload
    cv_analyzer.analyze.assert_not_called()
    mongo_repository.upsert_by_correlation_id.assert_not_called()


@pytest.mark.asyncio
async def test_upserts_and_publishes_success(job_message: CVAnalysisJobMessage) -> None:
    s3_client = AsyncMock()
    s3_client.get_file.return_value = BytesIO(b"%PDF-1.4\ncontent")

    pdf_loader = Mock()
    pdf_loader.load_with_metadata.return_value = PDFExtractionResult(
        text="x" * 250,
        page_count=2,
        char_count=250,
    )

    cv_analyzer = AsyncMock()
    cv_analyzer.analyze.return_value = CVData(user_name="Jane Doe")

    mongo_repository = AsyncMock()
    mongo_repository.upsert_by_correlation_id.return_value = "mongo-id-1"

    rabbitmq_producer = AsyncMock()

    use_case = CVAnalyzeUseCase(
        s3_client=s3_client,
        cv_analyzer=cv_analyzer,
        pdf_loader=pdf_loader,
        mongo_repository=mongo_repository,
        rabbitmq_producer=rabbitmq_producer,
    )

    await use_case(job_message.model_dump(mode="json"))

    mongo_repository.upsert_by_correlation_id.assert_awaited_once()
    rabbitmq_producer.send_message.assert_awaited_once()
    payload = rabbitmq_producer.send_message.await_args.args[0]
    assert '"status":"completed"' in payload
    assert "mongo-id-1" in payload


@pytest.mark.asyncio
async def test_publishes_failed_result_on_s3_error(job_message: CVAnalysisJobMessage) -> None:
    s3_client = AsyncMock()
    s3_client.get_file.side_effect = RuntimeError("network down")
    rabbitmq_producer = AsyncMock()

    use_case = CVAnalyzeUseCase(
        s3_client=s3_client,
        cv_analyzer=AsyncMock(),
        pdf_loader=Mock(),
        mongo_repository=AsyncMock(),
        rabbitmq_producer=rabbitmq_producer,
    )

    with pytest.raises(S3DownloadError):
        await use_case(job_message.model_dump(mode="json"))

    rabbitmq_producer.send_message.assert_awaited_once()


def _build_success_pipeline_mocks() -> tuple[AsyncMock, Mock, AsyncMock, AsyncMock, AsyncMock]:
    s3_client = AsyncMock()
    s3_client.get_file.return_value = BytesIO(b"%PDF-1.4\ncontent")

    pdf_loader = Mock()
    pdf_loader.load_with_metadata.return_value = PDFExtractionResult(
        text="x" * 250,
        page_count=2,
        char_count=250,
    )

    cv_analyzer = AsyncMock()
    cv_analyzer.analyze.return_value = CVData(user_name="Jane Doe")

    mongo_repository = AsyncMock()
    mongo_repository.upsert_by_correlation_id.return_value = "mongo-id-1"

    rabbitmq_producer = AsyncMock()
    return s3_client, pdf_loader, cv_analyzer, mongo_repository, rabbitmq_producer


@pytest.mark.asyncio
async def test_raises_llm_parse_error_and_publishes_failed(job_message: CVAnalysisJobMessage) -> None:
    s3_client, pdf_loader, cv_analyzer, mongo_repository, rabbitmq_producer = _build_success_pipeline_mocks()
    cv_analyzer.analyze.side_effect = ModelOutputParsingException("invalid schema")

    use_case = CVAnalyzeUseCase(
        s3_client=s3_client,
        cv_analyzer=cv_analyzer,
        pdf_loader=pdf_loader,
        mongo_repository=mongo_repository,
        rabbitmq_producer=rabbitmq_producer,
    )

    with pytest.raises(LLMParseError):
        await use_case(job_message.model_dump(mode="json"))

    rabbitmq_producer.send_message.assert_awaited_once()
    payload = rabbitmq_producer.send_message.await_args.args[0]
    assert '"status":"failed"' in payload
    assert "LLM_PARSE_ERROR" in payload


@pytest.mark.asyncio
async def test_raises_rate_limit_error_on_rate_limit_message(job_message: CVAnalysisJobMessage) -> None:
    s3_client, pdf_loader, cv_analyzer, mongo_repository, rabbitmq_producer = _build_success_pipeline_mocks()
    cv_analyzer.analyze.side_effect = Exception("Rate limit exceeded for model")

    use_case = CVAnalyzeUseCase(
        s3_client=s3_client,
        cv_analyzer=cv_analyzer,
        pdf_loader=pdf_loader,
        mongo_repository=mongo_repository,
        rabbitmq_producer=rabbitmq_producer,
    )

    with pytest.raises(LLMRateLimitError):
        await use_case(job_message.model_dump(mode="json"))

    rabbitmq_producer.send_message.assert_awaited_once()
    payload = rabbitmq_producer.send_message.await_args.args[0]
    assert "LLM_RATE_LIMIT" in payload


@pytest.mark.asyncio
async def test_downloads_pdf_from_bytesio_s3_response(job_message: CVAnalysisJobMessage) -> None:
    s3_client, pdf_loader, cv_analyzer, mongo_repository, rabbitmq_producer = _build_success_pipeline_mocks()
    s3_client.get_file.return_value = BytesIO(b"%PDF-1.4\nvalid-content")

    use_case = CVAnalyzeUseCase(
        s3_client=s3_client,
        cv_analyzer=cv_analyzer,
        pdf_loader=pdf_loader,
        mongo_repository=mongo_repository,
        rabbitmq_producer=rabbitmq_producer,
    )

    await use_case(job_message.model_dump(mode="json"))

    pdf_loader.load_with_metadata.assert_called_once()
    mongo_repository.upsert_by_correlation_id.assert_awaited_once()
