from dataclasses import dataclass

from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from src.agents.answer_evaluator.mapper import EvaluationMapper
from src.agents.answer_evaluator.prompts import EVALUATOR_INSTRUCTIONS, render_evaluator_context
from src.agents.answer_evaluator.schemas import EvaluationResultSchema
from src.agents.models import resolve_model
from src.domain.interfaces.ai.answer_evaluator import IAnswerEvaluator
from src.domain.value_objects.evaluation_request import EvaluationRequest
from src.domain.value_objects.evaluation_result import EvaluationResult
from src.domain.value_objects.focus_area import FocusArea
from src.domain.value_objects.interview_template import InterviewTemplate


@dataclass(frozen=True)
class EvaluatorDeps:
    template: InterviewTemplate
    target: FocusArea


def build_evaluator_agent(model: Model | str) -> Agent[EvaluatorDeps, EvaluationResultSchema]:
    agent: Agent[EvaluatorDeps, EvaluationResultSchema] = Agent(
        model,
        deps_type=EvaluatorDeps,
        output_type=EvaluationResultSchema,
        instructions=EVALUATOR_INSTRUCTIONS,
        model_settings={"temperature": 0.2},
        defer_model_check=True,
    )

    @agent.instructions
    def rubric(ctx: RunContext[EvaluatorDeps]) -> str:
        return render_evaluator_context(ctx.deps.template, ctx.deps.target)

    return agent


class AnswerEvaluator(IAnswerEvaluator):
    def __init__(self, model_specs: list[str], model: Model | None = None) -> None:
        self._model_specs = model_specs
        self._model = model
        self._agent: Agent[EvaluatorDeps, EvaluationResultSchema] | None = None

    async def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        if self._agent is None:
            self._agent = build_evaluator_agent(self._model or resolve_model(self._model_specs))
        prompt = f"Question:\n{request.question_text}\n\nCandidate answer:\n{request.answer_text}"
        result = await self._agent.run(prompt, deps=EvaluatorDeps(request.template, request.target_focus))
        return EvaluationMapper.to_domain(result.output)
