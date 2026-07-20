from typing import Any, Protocol

from shared_models.practice.attempt import ExerciseAttempt
from shared_models.practice.plan import PlanStatus, PracticePlan
from shared_models.practice.profile import UserPracticeProfile


class IPlanRepository(Protocol):
    """Persistence port for practice plans."""

    async def create_plan(self, plan: PracticePlan) -> PracticePlan:
        """Insert a new practice plan document."""
        pass

    async def get_plan(self, plan_id: str, user_id: str) -> PracticePlan | None:
        """Return a plan owned by the given user, or None if not found."""
        pass

    async def get_plan_status(self, plan_id: str, user_id: str):
        """Return lightweight status fields for a plan owned by the user."""
        pass

    async def get_plan_by_id(self, plan_id: str) -> PracticePlan | None:
        """Return a plan by identifier without ownership filtering."""
        pass

    async def get_plan_by_interview_session(self, interview_session_id: str) -> PracticePlan | None:
        """Return an interview-sourced plan for idempotency checks."""
        pass

    async def update_plan(self, plan_id: str, update_data: dict[str, Any]) -> bool:
        """Apply partial updates to a plan document."""
        pass

    async def try_claim_plan_generation(self, plan_id: str) -> PracticePlan | None:
        """Atomically transition pending → generating; return plan if claimed."""
        pass

    async def list_plans(
        self,
        user_id: str,
        *,
        skip: int = 0,
        limit: int = 20,
        status: PlanStatus | None = None,
    ) -> list[PracticePlan]:
        """List plans for a user with optional status filter and pagination."""
        pass

    async def ensure_indexes(self) -> None:
        """Create MongoDB indexes required by the plans collection."""
        pass


class IAttemptRepository(Protocol):
    """Persistence port for exercise attempts."""

    async def upsert_attempt(self, attempt: ExerciseAttempt) -> ExerciseAttempt:
        """Create or replace the single attempt allowed per exercise in MVP."""
        pass

    async def get_attempt(self, user_id: str, plan_id: str, exercise_id: str) -> ExerciseAttempt | None:
        """Return the attempt for a specific exercise, if it exists."""
        pass

    async def list_attempts(self, user_id: str, plan_id: str, exercise_id: str) -> list[ExerciseAttempt]:
        """List attempts for one exercise within a plan."""
        pass

    async def list_plan_attempts(self, user_id: str, plan_id: str) -> list[ExerciseAttempt]:
        """List all attempts submitted for a plan."""
        pass

    async def ensure_indexes(self) -> None:
        """Create MongoDB indexes required by the attempts collection."""
        pass


class IProfileRepository(Protocol):
    """Persistence port for user practice profiles."""

    async def get_profile(self, user_id: str) -> UserPracticeProfile | None:
        """Return the practice profile for a user, if it exists."""
        pass

    async def upsert_profile(self, profile: UserPracticeProfile) -> UserPracticeProfile:
        """Create or update a user practice profile."""
        pass

    async def ensure_indexes(self) -> None:
        """Create MongoDB indexes required by the profiles collection."""
        pass
