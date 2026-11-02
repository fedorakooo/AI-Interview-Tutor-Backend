import json

from langchain_core.prompts import ChatPromptTemplate

from src.legacy.agent.llm import get_interview_llm
from src.legacy.agent.prompts.soft_question import SOFT_QUESTION_PROMPT_HUMAN, SOFT_QUESTION_PROMPT_SYSTEM
from src.legacy.agent.utils.format_messages import format_messages
from src.legacy.domain.models.interview_state import InterviewState
from src.legacy.domain.value_objects.conversation_role import ConversationRole
from src.legacy.domain.value_objects.interview_stage import IntermediateInterviewStage
from src.legacy.services.company_presets import preset_context


async def ask_soft_question_node(state: InterviewState) -> InterviewState:
    state["soft_questions_turns"] += 1

    conversation_context = format_messages(state["messages"])

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SOFT_QUESTION_PROMPT_SYSTEM),
            ("human", SOFT_QUESTION_PROMPT_HUMAN),
        ]
    )

    chain = prompt | get_interview_llm("default")

    response = await chain.ainvoke(
        {
            "conversation_context": conversation_context,
            "cv_summary": json.dumps(state["cv_data"], indent=2),
            "company_preset_context": preset_context(state.get("company_preset")),
        }
    )
    content = response.content.strip()

    state["messages"].append((ConversationRole.AGENT, content))
    state["intermediate_stage"] = IntermediateInterviewStage.QUESTION

    return state
