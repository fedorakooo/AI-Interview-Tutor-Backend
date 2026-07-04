from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from src.adapters.outbound.pdf_loader import DoclingPDFLoader


@pytest.fixture
def minimal_pdf_bytes() -> BytesIO:
    return BytesIO(b"%PDF-1.4 minimal")


class TestDoclingPDFLoader:
    def test_load_seeks_stream_and_returns_markdown(self, minimal_pdf_bytes: BytesIO) -> None:
        mock_document = MagicMock()
        mock_document.export_to_markdown.return_value = "# John Doe\n\nSoftware Engineer"

        mock_result = MagicMock()
        mock_result.document = mock_document

        mock_converter = MagicMock()
        mock_converter.convert.return_value = mock_result

        with patch(
            "src.adapters.outbound.pdf_loader.DocumentConverter",
            return_value=mock_converter,
        ):
            loader = DoclingPDFLoader(do_ocr=False, do_table_structure=True)
            text = loader.load(minimal_pdf_bytes)

        assert text == "# John Doe\n\nSoftware Engineer"
        assert minimal_pdf_bytes.tell() == 0
        mock_converter.convert.assert_called_once()
        source = mock_converter.convert.call_args.args[0]
        assert source.name == "cv.pdf"
        assert source.stream is minimal_pdf_bytes

    def test_init_passes_ocr_and_table_options(self) -> None:
        with patch("src.adapters.outbound.pdf_loader.DocumentConverter") as mock_converter_cls:
            DoclingPDFLoader(do_ocr=True, do_table_structure=False)

        format_options = mock_converter_cls.call_args.kwargs["format_options"]
        pdf_option = next(iter(format_options.values()))
        pipeline_options = pdf_option.pipeline_options

        assert pipeline_options.do_ocr is True
        assert pipeline_options.do_table_structure is False
