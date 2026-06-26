from src.domain.models.interview_state import InterviewState
from src.domain.value_objects.interview_stage import OverallInterviewStage


def question_router_node(state: InterviewState) -> InterviewState:
    if state["is_answer_complete"]:
        if state["overall_stage"] == OverallInterviewStage.SOFT_QUESTIONS:
            state["soft_question_completed"] += 1
        if state["overall_stage"] == OverallInterviewStage.HARD_QUESTIONS:
            state["hard_question_completed"] += 1

    if state["overall_stage"] == OverallInterviewStage.SOFT_QUESTIONS and (
        state["soft_questions_turns"] > 8 or state["soft_question_completed"] >= 3
    ):
        state["overall_stage"] = OverallInterviewStage.HARD_QUESTIONS

    if state["overall_stage"] == OverallInterviewStage.HARD_QUESTIONS and (
        state["hard_questions_turns"] > 20 or state["hard_question_completed"] >= 8
    ):
        state["overall_stage"] = OverallInterviewStage.WRAP_UP

    return state
