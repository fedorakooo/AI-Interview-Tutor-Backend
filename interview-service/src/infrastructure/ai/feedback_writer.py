from pydantic_ai import Agent
from pydantic_ai.models import Model

from src.domain.interfaces.feedback_writer import IFeedbackWriter
from src.domain.interview.feedback import FeedbackDigest
from src.infrastructure.ai.models import resolve_model

FEEDBACK_INSTRUCTIONS = (
    "You write a short, warm and constructive feedback email for a job candidate after an interview. "
    "Use only the strengths and the growth topics you are given. Never mention scores, verdicts, ratings, "
    "comparisons with other candidates, hiring decisions, red flags or internal notes, and never promise or "
    "predict a hiring outcome. Suggest concrete topics to study for the growth areas. Write in the requested "
    "language, in plain text, in at most 150 words."
)


def render_digest(digest: FeedbackDigest) -> str:
    return "\n".join(
        [
            f"Language: {digest.language}",
            "Strengths: " + ("; ".join(digest.strengths) or "none"),
            "Growth topics: " + ("; ".join(digest.growth) or "none"),
        ]
    )


def build_feedback_agent(model: Model | str) -> Agent[None, str]:
    return Agent(
        model,
        output_type=str,
        instructions=FEEDBACK_INSTRUCTIONS,
        model_settings={"temperature": 0.5},
        defer_model_check=True,
    )


class PydanticFeedbackWriter(IFeedbackWriter):
    def __init__(self, model_specs: list[str], model: Model | None = None) -> None:
        self._model_specs = model_specs
        self._model = model
        self._agent: Agent[None, str] | None = None

    async def write(self, digest: FeedbackDigest) -> str:
        if self._agent is None:
            self._agent = build_feedback_agent(self._model or resolve_model(self._model_specs))
        result = await self._agent.run(render_digest(digest))
        return result.output.strip()
