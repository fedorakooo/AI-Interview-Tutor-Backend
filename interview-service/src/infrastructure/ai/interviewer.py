from collections.abc import AsyncIterator
from dataclasses import dataclass

from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from src.domain.interfaces.interviewer_agent import IInterviewerAgent
from src.domain.interview.dto import InterviewerRequest
from src.infrastructure.ai.models import resolve_model
from src.infrastructure.ai.prompts import INTERVIEWER_INSTRUCTIONS, render_interviewer_context


@dataclass(frozen=True)
class InterviewerDeps:
    request: InterviewerRequest


def build_interviewer_agent(model: Model | str) -> Agent[InterviewerDeps, str]:
    agent: Agent[InterviewerDeps, str] = Agent(
        model,
        deps_type=InterviewerDeps,
        output_type=str,
        instructions=INTERVIEWER_INSTRUCTIONS,
        model_settings={"temperature": 0.6},
        defer_model_check=True,
    )

    @agent.instructions
    def context(ctx: RunContext[InterviewerDeps]) -> str:
        return render_interviewer_context(ctx.deps.request)

    return agent


class PydanticInterviewerAgent(IInterviewerAgent):
    def __init__(self, model_specs: list[str], model: Model | None = None) -> None:
        self._model_specs = model_specs
        self._model = model
        self._agent: Agent[InterviewerDeps, str] | None = None

    async def stream_message(self, request: InterviewerRequest) -> AsyncIterator[str]:
        if self._agent is None:
            self._agent = build_interviewer_agent(self._model or resolve_model(self._model_specs))
        deps = InterviewerDeps(request)
        async with self._agent.run_stream("Write the next interviewer message.", deps=deps) as result:
            async for delta in result.stream_text(delta=True):
                yield delta
