from src.domain.models.interview_state import InterviewState
from src.domain.value_objects.interview_stage import OverallInterviewStage

BEHAVIORAL_ONLY = {"behavioral"}
TECHNICAL_ONLY = {"technical", "system_design", "coding"}


def question_router_node(state: InterviewState) -> InterviewState:
    mode = state.get("interview_mode", "mixed")

    if state["is_answer_complete"]:
        if state["overall_stage"] == OverallInterviewStage.SOFT_QUESTIONS:
            state["soft_question_completed"] += 1
        if state["overall_stage"] == OverallInterviewStage.HARD_QUESTIONS:
            state["hard_question_completed"] += 1

    soft_limit = 3 if mode not in TECHNICAL_ONLY else 0
    soft_turns = 8 if mode not in TECHNICAL_ONLY else 0
    hard_limit = 8 if mode not in BEHAVIORAL_ONLY else 0
    hard_turns = 20 if mode not in BEHAVIORAL_ONLY else 0

    if mode in BEHAVIORAL_ONLY:
        if state["overall_stage"] == OverallInterviewStage.SOFT_QUESTIONS and (
            state["soft_questions_turns"] > soft_turns or state["soft_question_completed"] >= soft_limit
        ):
            state["overall_stage"] = OverallInterviewStage.WRAP_UP
        return state

    if mode in TECHNICAL_ONLY:
        if state["overall_stage"] == OverallInterviewStage.SOFT_QUESTIONS:
            state["overall_stage"] = OverallInterviewStage.HARD_QUESTIONS
        if state["overall_stage"] == OverallInterviewStage.HARD_QUESTIONS and (
            state["hard_questions_turns"] > hard_turns or state["hard_question_completed"] >= hard_limit
        ):
            state["overall_stage"] = OverallInterviewStage.WRAP_UP
        return state

    if state["overall_stage"] == OverallInterviewStage.SOFT_QUESTIONS and (
        state["soft_questions_turns"] > 8 or state["soft_question_completed"] >= 3
    ):
        state["overall_stage"] = OverallInterviewStage.HARD_QUESTIONS

    if state["overall_stage"] == OverallInterviewStage.HARD_QUESTIONS and (
        state["hard_questions_turns"] > 20 or state["hard_question_completed"] >= 8
    ):
        state["overall_stage"] = OverallInterviewStage.WRAP_UP

    return state
