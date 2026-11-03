from abc import ABC, abstractmethod

from src.domain.interview.dto import EvaluationRequest, EvaluationResult


class IAnswerEvaluator(ABC):
    """LLM port for assessing candidate answers against a focus area."""

    @abstractmethod
    async def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        """Assess the latest candidate answer against the target focus area."""
