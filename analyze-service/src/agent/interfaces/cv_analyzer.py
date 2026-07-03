from abc import ABC, abstractmethod

from shared_models.cv.cv_data import CVData


class ICVAnalyzer(ABC):
    """Interface defining a CV analyzer."""

    @abstractmethod
    async def analyze(self, content: str) -> CVData:
        """
        Analyzes the raw text content of a resume.

        Raises:
            ModelOutputParsingException: If the LLM response cannot be parsed into CVData.
            CVParserException: Any other unexpected errors produced during invocation.
        """
        pass
