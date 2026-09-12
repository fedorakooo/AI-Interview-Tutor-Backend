from shared_models.cv.cv_data import CVData
from shared_models.interview.mode import InterviewMode, InterviewStartConfig

from src.domain.models.interview_state import InterviewState
from src.domain.models.user_profile import UserProfile
from src.domain.value_objects.interview_stage import IntermediateInterviewStage, OverallInterviewStage


def create_agent_initial_state(
    user: UserProfile,
    cv_data: CVData,
    start_config: InterviewStartConfig | None = None,
) -> InterviewState:
    config = start_config or InterviewStartConfig()
    overall = OverallInterviewStage.GREETING
    if config.mode == InterviewMode.TECHNICAL:
        overall = OverallInterviewStage.HARD_QUESTIONS
    elif config.mode == InterviewMode.BEHAVIORAL:
        overall = OverallInterviewStage.SOFT_QUESTIONS
    elif config.mode == InterviewMode.SYSTEM_DESIGN:
        overall = OverallInterviewStage.HARD_QUESTIONS
    elif config.mode == InterviewMode.CODING:
        overall = OverallInterviewStage.HARD_QUESTIONS

    return InterviewState(
        user_profile=user,
        messages=[],
        is_answer_complete=False,
        answer_score=None,
        answer_feedback=None,
        overall_stage=overall if config.mode != InterviewMode.MIXED else OverallInterviewStage.GREETING,
        cv_data=cv_data.model_dump(),
        intermediate_stage=IntermediateInterviewStage.SMALL_TALK,
        soft_questions_turns=0,
        soft_question_completed=0,
        hard_questions_turns=0,
        hard_question_completed=0,
        interview_report=None,
        interview_mode=config.mode.value,
        company_preset=config.company_preset,
        role_track=config.role_track,
        job_description=config.job_description,
        voice_enabled=config.voice_enabled,
        language=config.language,
    )
