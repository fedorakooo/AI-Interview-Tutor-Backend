from abc import ABC, abstractmethod

from src.domain.value_objects.assessment_digest import AssessmentDigest
from src.domain.value_objects.assessment_texts import AssessmentTexts


class IAssessmentTextWriter(ABC):
    """LLM port for writing the textual part of an assessment report."""

    @abstractmethod
    async def write(self, digest: AssessmentDigest) -> AssessmentTexts:
        """Write the rationale texts of the report for already computed verdicts."""
