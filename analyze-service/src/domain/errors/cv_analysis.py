from __future__ import annotations


class CVAnalysisError(Exception):
    """Base error for CV analysis pipeline failures."""

    code: str = "CV_ANALYSIS_ERROR"
    retryable: bool = False

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class EmptyPDFError(CVAnalysisError):
    code = "FILE_EMPTY"


class PDFTooLargeError(CVAnalysisError):
    code = "FILE_TOO_LARGE"


class InvalidPDFError(CVAnalysisError):
    code = "INVALID_PDF"


class ExtractionQualityError(CVAnalysisError):
    code = "EXTRACTION_EMPTY"


class S3DownloadError(CVAnalysisError):
    code = "S3_DOWNLOAD_FAILED"
    retryable = True


class LLMParseError(CVAnalysisError):
    code = "LLM_PARSE_ERROR"
    retryable = True


class LLMRateLimitError(CVAnalysisError):
    code = "LLM_RATE_LIMIT"
    retryable = True


class TransientAnalysisError(CVAnalysisError):
    code = "TRANSIENT_ERROR"
    retryable = True
