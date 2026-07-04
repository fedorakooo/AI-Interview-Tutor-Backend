from logging import Logger

from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from shared_models.cv.cv_data import CVData

from src.agent.errors.cv_parser import CVParserException, ModelOutputParsingException
from src.agent.interfaces.cv_analyzer import ICVAnalyzer
from src.agent.prompts.cv_parser import SYSTEM_CV_PARSER_PROMPT


class CVAnalyzer(ICVAnalyzer):
    """Parses resume content into a structured CVData object using an LLM."""

    def __init__(
        self,
        model: BaseChatModel,
        logger: Logger,
    ):
        self.logger = logger
        self._llm = model
        self._prompt = ChatPromptTemplate.from_messages(
            [("system", SYSTEM_CV_PARSER_PROMPT), ("user", "Resume Text:\n\n{content}")]
        )
        self._chain = self._prompt | self._llm.with_structured_output(CVData)

    async def analyze(self, content: str) -> CVData:
        try:
            cv_data: CVData = await self._chain.ainvoke({"content": content})
        except OutputParserException as exc:
            self.logger.error(f"Failed to parse LLM output into CVData structure: {exc}")
            raise ModelOutputParsingException(f"The model's output could not be parsed: {exc}") from exc
        except Exception as exc:
            self.logger.error(f"An unexpected error occurred during CV parsing: {exc}")
            raise CVParserException("An unexpected error occurred") from exc

        return cv_data
