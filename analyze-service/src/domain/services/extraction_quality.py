import re
import string

from src.domain.errors.cv_analysis import ExtractionQualityError
from src.domain.models.pdf_extraction_result import PDFExtractionResult

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
SECTION_KEYWORDS = ("experience", "education", "skills", "employment", "qualification")


def validate_extraction_quality(extraction: PDFExtractionResult) -> None:
    stripped = "".join(extraction.text.split())
    char_count = len(stripped)

    if char_count >= 200:
        return

    printable_chars = sum(1 for ch in extraction.text if ch in string.printable)
    total_chars = len(extraction.text) or 1
    printable_ratio = printable_chars / total_chars
    lowered = extraction.text.casefold()

    has_email = EMAIL_PATTERN.search(extraction.text) is not None
    has_keywords = any(keyword in lowered for keyword in SECTION_KEYWORDS)

    if printable_ratio >= 0.8 and (has_email or has_keywords):
        return

    raise ExtractionQualityError("Extracted text below quality threshold")
