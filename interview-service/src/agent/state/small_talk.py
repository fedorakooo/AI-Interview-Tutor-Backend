from langchain_core.prompts import ChatPromptTemplate

from src.agent.llm import llm
from src.agent.prompts.small_talk import SMALL_TALK_PROMPT_HUMAN, SMALL_TALK_PROMPT_SYSTEM
from src.agent.utils.format_messages import format_messages
from src.domain.models.interview_state import InterviewState
from src.domain.value_objects.conversation_role import ConversationRole


async def small_talk_node(state: InterviewState) -> InterviewState:
    messages = state["messages"]

    conversation_context = format_messages(messages)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SMALL_TALK_PROMPT_SYSTEM),
            ("human", SMALL_TALK_PROMPT_HUMAN),
        ]
    )

    chain = prompt | llm

    response = await chain.ainvoke({"conversation_context": conversation_context})
    content = response.content.strip()

    state["messages"].append((ConversationRole.AGENT, content))

    return state
