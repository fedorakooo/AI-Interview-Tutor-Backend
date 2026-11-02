from datetime import date

from shared_models.practice.profile import UserPracticeProfile


class StreakService:
    @staticmethod
    def update_on_completion(profile: UserPracticeProfile, *, practice_date: date | None = None) -> UserPracticeProfile:
        today = practice_date or date.today()
        if profile.last_practice_date == today:
            return profile
        if profile.last_practice_date and (today - profile.last_practice_date).days == 1:
            profile.current_streak_days += 1
        elif profile.last_practice_date != today:
            profile.current_streak_days = 1
        profile.last_practice_date = today
        return profile
