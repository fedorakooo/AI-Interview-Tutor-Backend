from langchain_core.prompts import ChatPromptTemplate
from langgraph.constants import END

from src.agent.llm import llm
from src.agent.prompts.wrap_up import WRAP_UP_PROMPT_HUMAN, WRAP_UP_PROMPT_SYSTEM
from src.agent.utils.format_messages import format_messages
from src.domain.models.interview_state import InterviewState
from src.domain.value_objects.conversation_role import ConversationRole


async def wrap_up_node(state: InterviewState) -> InterviewState:
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", WRAP_UP_PROMPT_SYSTEM),
            ("human", WRAP_UP_PROMPT_HUMAN),
        ]
    )

    conversation_context = format_messages(state["messages"])

    chain = prompt | llm
    response = await chain.ainvoke({"conversation_context": conversation_context})
    content = response.content.strip()

    state["messages"].append((ConversationRole.AGENT, content))
    state["overall_stage"] = END

    return state
