from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from src.agents.assessment_writer.mapper import AssessmentTextsMapper
from src.agents.assessment_writer.prompts import ASSESSMENT_INSTRUCTIONS, render_digest
from src.agents.assessment_writer.schemas import AssessmentTextsSchema
from src.agents.models import resolve_model
from src.domain.interfaces.ai.assessment_text_writer import IAssessmentTextWriter
from src.domain.value_objects.assessment_digest import AssessmentDigest
from src.domain.value_objects.assessment_texts import AssessmentTexts


def build_assessment_agent(model: Model | str) -> Agent[AssessmentDigest, AssessmentTextsSchema]:
    agent: Agent[AssessmentDigest, AssessmentTextsSchema] = Agent(
        model,
        deps_type=AssessmentDigest,
        output_type=AssessmentTextsSchema,
        instructions=ASSESSMENT_INSTRUCTIONS,
        model_settings={"temperature": 0.3},
        defer_model_check=True,
    )

    @agent.instructions
    def digest(ctx: RunContext[AssessmentDigest]) -> str:
        return render_digest(ctx.deps)

    return agent


class AssessmentTextWriter(IAssessmentTextWriter):
    def __init__(self, model_specs: list[str], model: Model | None = None) -> None:
        self._model_specs = model_specs
        self._model = model
        self._agent: Agent[AssessmentDigest, AssessmentTextsSchema] | None = None

    async def write(self, digest: AssessmentDigest) -> AssessmentTexts:
        if self._agent is None:
            self._agent = build_assessment_agent(self._model or resolve_model(self._model_specs))
        result = await self._agent.run("Write the report texts.", deps=digest)
        return AssessmentTextsMapper.to_domain(result.output)
