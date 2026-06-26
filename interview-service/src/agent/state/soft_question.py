import json

from langchain_core.prompts import ChatPromptTemplate

from src.agent.llm import llm
from src.agent.prompts.soft_question import SOFT_QUESTION_PROMPT_HUMAN, SOFT_QUESTION_PROMPT_SYSTEM
from src.agent.utils.format_messages import format_messages
from src.domain.models.interview_state import InterviewState
from src.domain.value_objects.conversation_role import ConversationRole
from src.domain.value_objects.interview_stage import IntermediateInterviewStage


async def ask_soft_question_node(state: InterviewState) -> InterviewState:
    state["soft_questions_turns"] += 1

    conversation_context = format_messages(state["messages"])

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SOFT_QUESTION_PROMPT_SYSTEM),
            ("human", SOFT_QUESTION_PROMPT_HUMAN),
        ]
    )

    chain = prompt | llm

    response = await chain.ainvoke(
        {
            "conversation_context": conversation_context,
            "cv_summary": json.dumps(state["cv_data"], indent=2),
        }
    )
    content = response.content.strip()

    state["messages"].append((ConversationRole.AGENT, content))
    state["intermediate_stage"] = IntermediateInterviewStage.QUESTION

    return state
