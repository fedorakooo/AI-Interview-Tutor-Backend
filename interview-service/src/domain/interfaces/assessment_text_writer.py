from abc import ABC, abstractmethod

from src.domain.interview.report_dto import AssessmentDigest, AssessmentTexts


class IAssessmentTextWriter(ABC):
    @abstractmethod
    async def write(self, digest: AssessmentDigest) -> AssessmentTexts:
        """Write the rationale texts of the report for already computed verdicts."""
