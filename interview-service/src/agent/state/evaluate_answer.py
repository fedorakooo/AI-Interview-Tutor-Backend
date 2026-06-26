import json

from langchain_core.prompts import ChatPromptTemplate

from src.agent.llm import llm
from src.agent.prompts.evaluate_answer import EVALUATE_ANSWER_PROMPT
from src.domain.models.interview_state import InterviewState


async def evaluate_answer_node(state: InterviewState) -> InterviewState:
    prompt = ChatPromptTemplate.from_template(EVALUATE_ANSWER_PROMPT)
    chain = prompt | llm
    response = await chain.ainvoke(
        {
            "question": state["messages"][-2][1],
            "answer": state["messages"][-1][1],
            "cv_context": json.dumps(state["cv_data"], indent=2),
        }
    )
    content = response.content.strip().lower()

    state["is_answer_complete"] = content == "complete"

    return state
