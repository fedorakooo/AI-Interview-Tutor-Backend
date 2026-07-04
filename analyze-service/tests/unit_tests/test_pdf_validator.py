import pytest
from src.domain.errors.cv_analysis import (
    EmptyPDFError,
    ExtractionQualityError,
    InvalidPDFError,
    PDFTooLargeError,
)
from src.domain.models.pdf_extraction_result import PDFExtractionResult
from src.domain.services.extraction_quality import validate_extraction_quality
from src.domain.services.pdf_validator import validate_pdf_bytes


class TestPDFValidator:
    def test_accepts_valid_pdf(self) -> None:
        validate_pdf_bytes(b"%PDF-1.4\n%test", max_size=1024)

    def test_rejects_empty_file(self) -> None:
        with pytest.raises(EmptyPDFError):
            validate_pdf_bytes(b"", max_size=1024)

    def test_rejects_invalid_magic_bytes(self) -> None:
        with pytest.raises(InvalidPDFError):
            validate_pdf_bytes(b"NOTPDF", max_size=1024)

    def test_rejects_oversized_file(self) -> None:
        with pytest.raises(PDFTooLargeError):
            validate_pdf_bytes(b"%PDF-" + b"x" * 20, max_size=10)


class TestExtractionQuality:
    def test_accepts_long_text(self) -> None:
        validate_extraction_quality(
            PDFExtractionResult(
                text="x" * 250,
                page_count=1,
                char_count=250,
            )
        )

    def test_rejects_short_unstructured_text(self) -> None:
        with pytest.raises(ExtractionQualityError):
            validate_extraction_quality(
                PDFExtractionResult(
                    text="abc",
                    page_count=1,
                    char_count=3,
                )
            )

    def test_accepts_short_text_with_email(self) -> None:
        validate_extraction_quality(
            PDFExtractionResult(
                text="Contact: john.doe@example.com\nExperience: backend developer",
                page_count=1,
                char_count=60,
            )
        )
