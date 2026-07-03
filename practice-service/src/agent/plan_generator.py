import json

from langchain_core.prompts import ChatPromptTemplate
from shared_models.practice.plan import PracticePlanDraft
from src.agent.prompts.templates import PLAN_GENERATION_SYSTEM_PROMPT
from src.application.services.practice_services import BuiltPlanContext
from src.infrastructure.llm.factory import LLMFactory
from src.logger import agent_logger


class PlanGenerator:
    def __init__(self) -> None:
        self._llm = LLMFactory.create_llm().with_structured_output(PracticePlanDraft)
        self._prompt = ChatPromptTemplate.from_messages(
            [
                ("system", PLAN_GENERATION_SYSTEM_PROMPT),
                (
                    "human",
                    "Create a practice plan using this context JSON:\n{context_json}\n"
                    "Return exactly {exercise_count} exercises of types: {exercise_types}.",
                ),
            ]
        )

    async def generate(self, context: BuiltPlanContext) -> PracticePlanDraft:
        context_json = json.dumps(
            {
                "focus_skills": context.focus_skills,
                "difficulty": context.difficulty,
                "context_snapshot": context.context_snapshot.model_dump(mode="json"),
                "title_hint": context.title_hint,
            },
            ensure_ascii=True,
        )
        chain = self._prompt | self._llm
        agent_logger.info("Generating practice plan for skills: %s", context.focus_skills)
        result = await chain.ainvoke(
            {
                "context_json": context_json,
                "exercise_count": context.exercise_count,
                "exercise_types": ", ".join(exercise_type.value for exercise_type in context.exercise_types),
            }
        )
        if isinstance(result, PracticePlanDraft):
            return result
        return PracticePlanDraft.model_validate(result)
