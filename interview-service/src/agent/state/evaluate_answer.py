import json
import re

from langchain_core.prompts import ChatPromptTemplate

from src.agent.llm import get_interview_llm
from src.agent.prompts.evaluate_answer import EVALUATE_ANSWER_PROMPT
from src.domain.models.interview_state import InterviewState


def _parse_evaluation(content: str) -> tuple[bool, float | None, str | None]:
    text = content.strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        payload = json.loads(text)
        complete = bool(payload.get("complete", False))
        score_raw = payload.get("score")
        score = float(score_raw) if score_raw is not None else None
        if score is not None:
            score = max(0.0, min(10.0, score))
        feedback = payload.get("feedback")
        feedback_str = str(feedback).strip() if feedback else None
        return complete, score, feedback_str
    except (json.JSONDecodeError, TypeError, ValueError):
        lowered = text.lower()
        if lowered == "complete":
            return True, None, None
        if lowered == "incomplete":
            return False, None, None
        match = re.search(r'"?complete"?\s*:\s*(true|false)', lowered)
        if match:
            return match.group(1) == "true", None, None
        return lowered == "complete", None, None


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
