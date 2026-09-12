import json

from langchain_core.prompts import ChatPromptTemplate

from src.agent.llm import get_interview_llm
from src.agent.prompts.evaluate_answer import EVALUATE_ANSWER_PROMPT
from src.agent.state.evaluate_answer_parser import parse_evaluation
from src.domain.models.interview_state import InterviewState


def _parse_evaluation(content: str) -> tuple[bool, float | None, str | None]:
    return parse_evaluation(content)


async def evaluate_answer_node(state: InterviewState) -> InterviewState:
    prompt = ChatPromptTemplate.from_template(EVALUATE_ANSWER_PROMPT)
    chain = prompt | get_interview_llm("evaluate_answer")
    response = await chain.ainvoke(
        {
            "question": state["messages"][-2][1],
            "answer": state["messages"][-1][1],
            "cv_context": json.dumps(state["cv_data"], indent=2),
        }
    )
    complete, score, feedback = _parse_evaluation(str(response.content))

    state["is_answer_complete"] = complete
    state["answer_score"] = score
    state["answer_feedback"] = feedback

    return state
