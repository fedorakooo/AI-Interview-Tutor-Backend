from logging import Logger

from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import ValidationError
from shared_models.cv.cv_data import CVData

from src.agent.errors import CVParserException, ModelOutputParsingException
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
            [SystemMessage(content=SYSTEM_CV_PARSER_PROMPT), ("user", "Resume Text:\n\n{content}")]
        )
        self._chain = self._prompt | self._llm.with_structured_output(CVData)

    async def analyze(self, content: str) -> CVData:
        try:
            result = await self._chain.ainvoke({"content": content})
            cv_data = CVData.model_validate(result)
        except (OutputParserException, ValidationError) as exc:
            self.logger.error("LLM response did not match the CV schema")
            raise ModelOutputParsingException("LLM response did not match the CV schema") from exc
        except Exception as exc:
            self.logger.error("CV extraction failed (%s)", type(exc).__name__)
            raise CVParserException("An unexpected error occurred") from exc

        if not any(cv_data.model_dump().values()):
            raise ModelOutputParsingException("LLM response contained no CV information")
        return cv_data
