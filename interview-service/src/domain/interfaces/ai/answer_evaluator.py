from abc import ABC, abstractmethod

from src.domain.value_objects.evaluation_request import EvaluationRequest
from src.domain.value_objects.evaluation_result import EvaluationResult


class IAnswerEvaluator(ABC):
    """LLM port for assessing candidate answers against a focus area."""

    @abstractmethod
    async def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        """Assess the latest candidate answer against the target focus area."""
