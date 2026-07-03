from io import BytesIO

from docling.datamodel.base_models import DocumentStream, InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
from docling.document_converter import DocumentConverter, PdfFormatOption

from src.domain.adapters.outbound.pdf_loader import IPDFLoader
from src.domain.models.pdf_extraction_result import PDFExtractionResult


class DoclingPDFLoader(IPDFLoader):
    """Extracts PDF content as Markdown using Docling layout analysis and optional OCR."""

    def __init__(self, do_ocr: bool = True, do_table_structure: bool = True) -> None:
        options = PdfPipelineOptions(do_ocr=do_ocr, do_table_structure=do_table_structure)
        options.table_structure_options.mode = TableFormerMode.ACCURATE
        self._converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
        )

    def load(self, pdf_bytes: BytesIO) -> str:
        return self.load_with_metadata(pdf_bytes).text

    def load_with_metadata(self, pdf_bytes: BytesIO) -> PDFExtractionResult:
        pdf_bytes.seek(0)
        source = DocumentStream(name="cv.pdf", stream=pdf_bytes)
        result = self._converter.convert(source)
        text = result.document.export_to_markdown()
        page_count = len(result.document.pages) if result.document.pages else 1
        warnings: list[str] = []
        if len("".join(text.split())) < 200:
            warnings.append("low_char_count")

        return PDFExtractionResult(
            text=text,
            method="docling",
            page_count=max(page_count, 1),
            char_count=len(text),
            warnings=warnings,
        )
