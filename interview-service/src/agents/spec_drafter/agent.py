from pydantic_ai import Agent
from pydantic_ai.models import Model

from src.agents.models import resolve_model
from src.agents.spec_drafter.mapper import SpecDraftMapper
from src.agents.spec_drafter.prompts import SPEC_INSTRUCTIONS, render_request
from src.agents.spec_drafter.schemas import SpecDraftSchema
from src.domain.interfaces.ai.spec_drafter import ISpecDrafter
from src.domain.value_objects.draft_brief import DraftBrief
from src.domain.value_objects.spec_draft import SpecDraft


def build_spec_agent(model: Model | str) -> Agent[None, SpecDraftSchema]:
    return Agent(
        model,
        output_type=SpecDraftSchema,
        instructions=SPEC_INSTRUCTIONS,
        model_settings={"temperature": 0.3},
        defer_model_check=True,
    )


class SpecDrafter(ISpecDrafter):
    def __init__(self, model_specs: list[str], model: Model | None = None) -> None:
        self._model_specs = model_specs
        self._model = model
        self._agent: Agent[None, SpecDraftSchema] | None = None

    async def draft(self, request: DraftBrief) -> SpecDraft:
        if self._agent is None:
            self._agent = build_spec_agent(self._model or resolve_model(self._model_specs))
        result = await self._agent.run(render_request(request))
        return SpecDraftMapper.to_domain(result.output)
