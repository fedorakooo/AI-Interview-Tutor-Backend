from abc import ABC, abstractmethod
from io import BytesIO

from src.domain.models.pdf_extraction_result import PDFExtractionResult


class IPDFLoader(ABC):
    """Interface defining the interface for loading PDF documents."""

    @abstractmethod
    def load(self, pdf_bytes: BytesIO) -> str:
        """Loads PDF content from a BytesIO object and returns all text."""
        pass

    @abstractmethod
    def load_with_metadata(self, pdf_bytes: BytesIO) -> PDFExtractionResult:
        """Loads PDF content and returns text with extraction metadata."""
        pass
