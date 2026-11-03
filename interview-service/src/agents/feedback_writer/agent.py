from pydantic_ai import Agent
from pydantic_ai.models import Model

from src.agents.feedback_writer.prompts import FEEDBACK_INSTRUCTIONS, render_digest
from src.agents.models import resolve_model
from src.domain.interfaces.ai.feedback_writer import IFeedbackWriter
from src.domain.value_objects.feedback_digest import FeedbackDigest


def build_feedback_agent(model: Model | str) -> Agent[None, str]:
    return Agent(
        model,
        output_type=str,
        instructions=FEEDBACK_INSTRUCTIONS,
        model_settings={"temperature": 0.5},
        defer_model_check=True,
    )


class FeedbackWriter(IFeedbackWriter):
    def __init__(self, model_specs: list[str], model: Model | None = None) -> None:
        self._model_specs = model_specs
        self._model = model
        self._agent: Agent[None, str] | None = None

    async def write(self, digest: FeedbackDigest) -> str:
        if self._agent is None:
            self._agent = build_feedback_agent(self._model or resolve_model(self._model_specs))
        result = await self._agent.run(render_digest(digest))
        return result.output.strip()
