from typing import Any, TypedDict

from src.domain.models.user_profile import UserProfile
from src.domain.value_objects.conversation_role import ConversationRole
from src.domain.value_objects.interview_stage import IntermediateInterviewStage, OverallInterviewStage


class InterviewState(TypedDict):
    user_profile: UserProfile
    messages: list[tuple[ConversationRole, str]]
    cv_data: dict[str, Any]

    overall_stage: OverallInterviewStage
    intermediate_stage: IntermediateInterviewStage

    is_answer_complete: bool
    answer_score: float | None
    answer_feedback: str | None

    soft_questions_turns: int
    soft_question_completed: int

    hard_questions_turns: int
    hard_question_completed: int

    interview_report: dict[str, Any] | None

    interview_mode: str
    company_preset: str | None
    role_track: str | None
    job_description: str | None
    voice_enabled: bool
    language: str
