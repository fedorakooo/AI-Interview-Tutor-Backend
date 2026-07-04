from shared_models.interview.report import SkillScore
from shared_models.practice.exercise import ExerciseType
from shared_models.practice.messaging import PlanGenerationRequest
from shared_models.practice.plan import PlanContextSnapshot, PlanSource
from shared_models.practice.profile import UserPracticeProfile
from src.application.services.practice_services import BuiltPlanContext
from src.infrastructure.mongo.context_reader import ContextReader

DEFAULT_FOCUS_SKILLS = ["General CS", "Problem Solving"]
LOW_SCORE_THRESHOLD = 6.0


class PlanContextBuilder:
    def __init__(self, context_reader: ContextReader) -> None:
        self._context_reader = context_reader

    async def build(
        self,
        user_id: str,
        request: PlanGenerationRequest,
        profile: UserPracticeProfile,
        *,
        interview_session_id: str | None = None,
    ) -> BuiltPlanContext:
        cv_context = await self._context_reader.get_latest_cv(user_id) if request.include_cv_context else None
        interview_context = None
        if request.include_interview_context:
            if interview_session_id:
                interview_context = await self._context_reader.get_interview_by_session(interview_session_id)
            else:
                interview_context = await self._context_reader.get_latest_interview(user_id)

        difficulty = request.difficulty or profile.preferred_difficulty
        exercise_types = request.exercise_types or profile.preferred_exercise_types
        if not exercise_types:
            exercise_types = [
                ExerciseType.MCQ_SINGLE,
                ExerciseType.OPEN_QUESTION,
                ExerciseType.FLASHCARD,
            ]

        focus_skills = self._merge_focus_skills(request, profile, interview_context, cv_context)
        source = self._derive_source(cv_context, interview_context, profile, request)
        user_goals = [goal.skill for goal in profile.development_goals]

        snapshot = PlanContextSnapshot(
            focus_skills=focus_skills,
            cv_specialization=cv_context.cv_data.specialization if cv_context else None,
            cv_top_skills=self._extract_cv_skills(cv_context)[:5] if cv_context else [],
            interview_weaknesses=interview_context.report.weaknesses if interview_context else [],
            interview_low_scores=self._low_scores(interview_context.report.skill_scores if interview_context else []),
            user_goals=user_goals,
            difficulty=difficulty,
            exercise_types_requested=exercise_types,
        )

        return BuiltPlanContext(
            focus_skills=focus_skills,
            difficulty=difficulty.value,
            exercise_types=exercise_types,
            exercise_count=request.exercise_count,
            source=source.value,
            context_snapshot=snapshot,
            interview_session_id=interview_context.session_id if interview_context else None,
            cv_correlation_id=cv_context.correlation_id if cv_context else None,
            title_hint=request.title_hint,
            user_goals=user_goals,
        )

    def _merge_focus_skills(self, request, profile, interview_context, cv_context) -> list[str]:
        merged: list[str] = []
        for skill in request.focus_skills:
            if skill and skill not in merged:
                merged.append(skill)
        for goal in profile.development_goals:
            if goal.skill not in merged:
                merged.append(goal.skill)
        if interview_context:
            for weakness in interview_context.report.weaknesses:
                if weakness not in merged:
                    merged.append(weakness)
            for score in interview_context.report.skill_scores:
                if score.score < LOW_SCORE_THRESHOLD and score.skill not in merged:
                    merged.append(score.skill)
        if cv_context:
            for skill in self._extract_cv_skills(cv_context):
                if skill not in merged:
                    merged.append(skill)
                if len(merged) >= 10:
                    break
        if not merged:
            merged = DEFAULT_FOCUS_SKILLS.copy()
        return merged[:10]

    @staticmethod
    def _derive_source(cv_context, interview_context, profile, request) -> PlanSource:
        has_goals = bool(profile.development_goals or request.focus_skills)
        has_cv = cv_context is not None
        has_interview = interview_context is not None
        if has_cv and (has_interview or has_goals):
            return PlanSource.COMBINED
        if has_cv:
            return PlanSource.CV
        if has_interview:
            return PlanSource.INTERVIEW
        if has_goals:
            return PlanSource.MANUAL
        return PlanSource.MANUAL

    @staticmethod
    def _extract_cv_skills(cv_context) -> list[str]:
        skills = cv_context.cv_data.skills or []
        return [skill.name for skill in skills if skill.name]

    @staticmethod
    def _low_scores(skill_scores: list[SkillScore]) -> list[SkillScore]:
        return [score for score in skill_scores if score.score < LOW_SCORE_THRESHOLD]
