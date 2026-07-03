import asyncio
import time
from datetime import UTC, datetime
from io import BytesIO
from typing import Any

from shared_models.cv.cv_data import CVData
from shared_models.messaging.common import AnalysisStatus, ExtractionMetadata
from shared_models.messaging.cv_analysis import CVAnalysisDocument, CVAnalysisJobMessage, CVAnalysisResultMessage

from src.agent.errors.cv_parser import CVParserException, ModelOutputParsingException
from src.agent.interfaces.cv_analyzer import ICVAnalyzer
from src.config import settings
from src.domain.adapters.outbound.mongo import IMongoRepository
from src.domain.adapters.outbound.pdf_loader import IPDFLoader
from src.domain.adapters.outbound.rabbitmq_producer import IRabbitMQProducer
from src.domain.adapters.outbound.s3 import IS3Client
from src.domain.errors.cv_analysis import (
    CVAnalysisError,
    LLMParseError,
    LLMRateLimitError,
    S3DownloadError,
    TransientAnalysisError,
)
from src.domain.models.pdf_extraction_result import PDFExtractionResult
from src.domain.services.extraction_quality import validate_extraction_quality
from src.domain.services.pdf_validator import validate_pdf_bytes


class CVAnalyzeUseCase:
    def __init__(
        self,
        s3_client: IS3Client,
        cv_analyzer: ICVAnalyzer,
        pdf_loader: IPDFLoader,
        mongo_repository: IMongoRepository,
        rabbitmq_producer: IRabbitMQProducer,
    ):
        self.s3_client = s3_client
        self.cv_analyzer = cv_analyzer
        self.pdf_loader = pdf_loader
        self.mongo_repository = mongo_repository
        self.rabbitmq_producer = rabbitmq_producer

    async def __call__(self, event_data: dict[str, Any]) -> None:
        job = CVAnalysisJobMessage.model_validate(event_data)
        started_at = time.monotonic()
        extraction: PDFExtractionResult | None = None

        try:
            pdf_bytes = await self._download_pdf(job.s3_object_key)
            validate_pdf_bytes(pdf_bytes, settings.s3_settings.cv_max_upload_bytes)

            extraction = await asyncio.to_thread(self.pdf_loader.load_with_metadata, BytesIO(pdf_bytes))
            validate_extraction_quality(extraction)

            analysis_result = await self._analyze_cv(extraction.text)
            document = self._build_mongo_document(job, analysis_result, extraction, started_at)
            doc_id = await self.mongo_repository.upsert_by_correlation_id(
                correlation_id=str(job.correlation_id),
                document=document,
            )

            await self._publish_result(
                job,
                status=AnalysisStatus.COMPLETED,
                mongo_document_id=doc_id,
                extraction=extraction,
            )
        except CVAnalysisError as exc:
            await self._publish_result(
                job,
                status=AnalysisStatus.FAILED,
                error_code=exc.code,
                error_message=exc.message,
                extraction=extraction,
            )
            raise

    async def _download_pdf(self, s3_object_key: str) -> bytes:
        try:
            payload = await self.s3_client.get_file(s3_object_key)
            if isinstance(payload, BytesIO):
                return payload.getvalue()
            return payload
        except Exception as exc:
            raise S3DownloadError(f"Failed to download PDF from S3: {exc}") from exc

    async def _analyze_cv(self, content: str) -> CVData:
        try:
            return await self.cv_analyzer.analyze(content=content)
        except ModelOutputParsingException as exc:
            raise LLMParseError(str(exc)) from exc
        except CVParserException as exc:
            raise LLMParseError(str(exc)) from exc
        except Exception as exc:
            message = str(exc).lower()
            if "rate" in message and "limit" in message:
                raise LLMRateLimitError(str(exc)) from exc
            if isinstance(exc, TimeoutError):
                raise TransientAnalysisError(str(exc)) from exc
            raise

    def _build_mongo_document(
        self,
        job: CVAnalysisJobMessage,
        analysis_result: CVData,
        extraction: PDFExtractionResult,
        started_at: float,
    ) -> dict[str, Any]:
        analyzed_at = datetime.now(UTC)
        duration_ms = int((time.monotonic() - started_at) * 1000)
        extraction_metadata = ExtractionMetadata(
            method=extraction.method,
            page_count=extraction.page_count,
            char_count=extraction.char_count,
            duration_ms=duration_ms,
            warnings=extraction.warnings,
        )
        analysis_document = CVAnalysisDocument(
            correlation_id=job.correlation_id,
            user_id=job.user_id,
            s3_object_key=job.s3_object_key,
            status=AnalysisStatus.COMPLETED,
            published_at=job.published_at,
            analyzed_at=analyzed_at,
            extraction_metadata=extraction_metadata,
            cv=analysis_result,
        )
        return analysis_document.to_mongo_dict()

    async def _publish_result(
        self,
        job: CVAnalysisJobMessage,
        *,
        status: AnalysisStatus,
        mongo_document_id: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        extraction: PDFExtractionResult | None = None,
    ) -> None:
        extraction_metadata = None
        if extraction is not None:
            extraction_metadata = ExtractionMetadata(
                method=extraction.method,
                page_count=extraction.page_count,
                char_count=extraction.char_count,
                duration_ms=0,
                warnings=extraction.warnings,
            )

        result_message = CVAnalysisResultMessage(
            correlation_id=job.correlation_id,
            user_id=job.user_id,
            s3_object_key=job.s3_object_key,
            status=status,
            mongo_document_id=mongo_document_id,
            error_code=error_code,
            error_message=error_message,
            extraction_metadata=extraction_metadata,
            published_at=datetime.now(UTC),
        )
        await self.rabbitmq_producer.send_message(result_message.model_dump_json())
