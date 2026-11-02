from datetime import UTC, datetime

from shared_models.practice.profile import UserPracticeProfile
from src.domain.exceptions.practice_errors import DailyPlanQuotaExceededError
from src.domain.interfaces.repositories import IProfileRepository


class QuotaService:
    def __init__(self, profile_repository: IProfileRepository) -> None:
        self._profiles = profile_repository

    async def check_and_increment(self, profile: UserPracticeProfile) -> UserPracticeProfile:
        profile = await self._profiles.reset_quota_if_needed(profile)
        if profile.plans_generated_today >= profile.daily_plan_quota:
            raise DailyPlanQuotaExceededError()
        profile.plans_generated_today += 1
        profile.updated_at = datetime.now(UTC)
        return profile
