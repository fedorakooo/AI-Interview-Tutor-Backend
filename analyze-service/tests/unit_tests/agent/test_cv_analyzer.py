import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.exceptions import OutputParserException
from shared_models.cv.cv_data import CVData

from src.agent.errors.cv_parser import ModelOutputParsingException
from src.agent.services.cv_analyzer import CVAnalyzer


@pytest.fixture
def logger() -> logging.Logger:
    return logging.getLogger("test.cv_analyzer")


@pytest.mark.asyncio
async def test_returns_structured_cv_data(logger: logging.Logger) -> None:
    model = MagicMock()
    expected = CVData(user_name="Jane Doe")
    chain = AsyncMock()
    chain.ainvoke.return_value = expected
    analyzer = CVAnalyzer(model=model, logger=logger)
    analyzer._chain = chain

    result = await analyzer.analyze(content="Senior Python Developer")

    assert result == expected
    chain.ainvoke.assert_awaited_once_with({"content": "Senior Python Developer"})


@pytest.mark.asyncio
async def test_raises_model_output_parsing_exception(logger: logging.Logger) -> None:
    model = MagicMock()
    chain = AsyncMock()
    chain.ainvoke.side_effect = OutputParserException("invalid json")
    analyzer = CVAnalyzer(model=model, logger=logger)
    analyzer._chain = chain

    with pytest.raises(ModelOutputParsingException):
        await analyzer.analyze(content="Resume text")
