from dataclasses import dataclass

from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model
from shared_models.assessment import AssessmentTemplateSnapshot, FocusArea

from src.domain.interfaces.answer_evaluator import IAnswerEvaluator
from src.domain.interview.dto import EvaluationRequest, EvaluationResult
from src.infrastructure.ai.models import resolve_model
from src.infrastructure.ai.prompts import EVALUATOR_INSTRUCTIONS, render_evaluator_context


@dataclass(frozen=True)
class EvaluatorDeps:
    template: AssessmentTemplateSnapshot
    target: FocusArea


def build_evaluator_agent(model: Model | str) -> Agent[EvaluatorDeps, EvaluationResult]:
    agent: Agent[EvaluatorDeps, EvaluationResult] = Agent(
        model,
        deps_type=EvaluatorDeps,
        output_type=EvaluationResult,
        instructions=EVALUATOR_INSTRUCTIONS,
        model_settings={"temperature": 0.2},
        defer_model_check=True,
    )

    @agent.instructions
    def rubric(ctx: RunContext[EvaluatorDeps]) -> str:
        return render_evaluator_context(ctx.deps.template, ctx.deps.target)

    return agent


class PydanticAnswerEvaluator(IAnswerEvaluator):
    def __init__(self, model_specs: list[str], model: Model | None = None) -> None:
        self._model_specs = model_specs
        self._model = model
        self._agent: Agent[EvaluatorDeps, EvaluationResult] | None = None

    async def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        if self._agent is None:
            self._agent = build_evaluator_agent(self._model or resolve_model(self._model_specs))
        prompt = f"Question:\n{request.question_text}\n\nCandidate answer:\n{request.answer_text}"
        result = await self._agent.run(prompt, deps=EvaluatorDeps(request.template, request.target_focus))
        return result.output
