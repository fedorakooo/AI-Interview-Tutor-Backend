from src.domain.models.cv_data import CVData
from src.domain.models.interview_state import InterviewState
from src.domain.models.user_profile import UserProfile
from src.domain.value_objects.interview_stage import IntermediateInterviewStage, OverallInterviewStage


def create_agent_initial_state(user: UserProfile, cv_data: CVData) -> InterviewState:
    return InterviewState(
        user_profile=user,
        messages=[],
        is_answer_complete=False,
        overall_stage=OverallInterviewStage.GREETING,
        cv_data=cv_data.model_dump(),
        intermediate_stage=IntermediateInterviewStage.SMALL_TALK,
        soft_questions_turns=0,
        soft_question_completed=0,
        hard_questions_turns=0,
        hard_question_completed=0,
    )
