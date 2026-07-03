from datetime import UTC, datetime
from uuid import UUID

from shared_models.practice.profile import DevelopmentGoal, UserPracticeProfile
from src.domain.exceptions.practice_errors import PracticeServiceError


class GetProfileUseCase:
    def __init__(self, profile_repository) -> None:
        self._profiles = profile_repository

    async def execute(self, user_id: UUID) -> UserPracticeProfile:
        profile = await self._profiles.get_profile(str(user_id))
        if profile is None:
            profile = self._profiles.default_profile(user_id)
            await self._profiles.upsert_profile(profile)
        return await self._profiles.reset_quota_if_needed(profile)


class UpdateProfileUseCase:
    def __init__(self, profile_repository) -> None:
        self._profiles = profile_repository

    async def execute(self, user_id: UUID, update_data: dict) -> UserPracticeProfile:
        profile = await self._profiles.get_profile(str(user_id))
        if profile is None:
            profile = self._profiles.default_profile(user_id)

        if "development_goals" in update_data and update_data["development_goals"] is not None:
            goals = [DevelopmentGoal.model_validate(goal) for goal in update_data["development_goals"]]
            if len(goals) > 10:
                raise PracticeServiceError("Too many development goals", error_code="INVALID_PROFILE")
            profile.development_goals = goals
        if update_data.get("preferred_difficulty") is not None:
            profile.preferred_difficulty = update_data["preferred_difficulty"]
        if update_data.get("preferred_exercise_types") is not None:
            profile.preferred_exercise_types = update_data["preferred_exercise_types"]
        if update_data.get("weekly_target_minutes") is not None:
            minutes = update_data["weekly_target_minutes"]
            if not (15 <= minutes <= 600):
                raise PracticeServiceError("weekly_target_minutes out of range", error_code="INVALID_PROFILE")
            profile.weekly_target_minutes = minutes

        profile.updated_at = datetime.now(UTC)
        return await self._profiles.upsert_profile(profile)
