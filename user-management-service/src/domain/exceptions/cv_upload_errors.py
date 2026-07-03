class CVUploadError(Exception):
    """Base error for CV upload validation and orchestration failures."""

    def __init__(self, message: str, error_code: str, http_status: int) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.http_status = http_status


class EmptyFileError(CVUploadError):
    def __init__(self) -> None:
        super().__init__("Uploaded file is empty", "FILE_EMPTY", 400)


class FileTooLargeError(CVUploadError):
    def __init__(self, max_size: int) -> None:
        super().__init__(f"File exceeds maximum size of {max_size} bytes", "FILE_TOO_LARGE", 413)


class InvalidPDFError(CVUploadError):
    def __init__(self) -> None:
        super().__init__("File does not appear to be a valid PDF", "INVALID_PDF", 400)


class UnsupportedMediaTypeError(CVUploadError):
    def __init__(self) -> None:
        super().__init__("Only application/pdf uploads are supported", "UNSUPPORTED_MEDIA_TYPE", 415)


class S3UploadFailedError(CVUploadError):
    def __init__(self, message: str = "Failed to upload CV to object storage") -> None:
        super().__init__(message, "S3_UPLOAD_FAILED", 503)


class PublishFailedError(CVUploadError):
    def __init__(self, message: str = "Failed to publish CV analysis job") -> None:
        super().__init__(message, "PUBLISH_FAILED", 503)
