from src.domain.errors.cv_analysis import EmptyPDFError, InvalidPDFError, PDFTooLargeError

PDF_MAGIC = b"%PDF-"


def validate_pdf_bytes(data: bytes, max_size: int) -> None:
    if len(data) == 0:
        raise EmptyPDFError("Uploaded PDF is empty")
    if len(data) > max_size:
        raise PDFTooLargeError(f"PDF exceeds maximum size of {max_size} bytes")
    if not data[:5].startswith(PDF_MAGIC):
        raise InvalidPDFError("File does not appear to be a valid PDF")
