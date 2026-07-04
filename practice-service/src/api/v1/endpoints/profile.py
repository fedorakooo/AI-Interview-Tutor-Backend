from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jwt_handler.value_objects import AccessTokenPayload
from pydantic import BaseModel, Field
from shared_models.practice.exercise import ExerciseType
from shared_models.practice.profile import DevelopmentGoal, DifficultyLevel, UserPracticeProfile
from src.api.security import require_authenticated
from src.app.container import get_container, get_user_id
from src.domain.exceptions.practice_errors import PracticeServiceError

router = APIRouter(prefix="/practice", tags=["Practice Profile"])


class UpdateProfileRequest(BaseModel):
    development_goals: list[DevelopmentGoal] | None = None
    preferred_difficulty: DifficultyLevel | None = None
    preferred_exercise_types: list[ExerciseType] | None = None
    weekly_target_minutes: int | None = Field(default=None, ge=15, le=600)


@router.get("/profile", response_model=UserPracticeProfile)
async def get_profile(
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    request: Request,
) -> UserPracticeProfile:
    container = get_container(request)
    return await container.get_profile_use_case.execute(get_user_id(payload))


@router.put("/profile", response_model=UserPracticeProfile)
async def update_profile(
    body: UpdateProfileRequest,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    request: Request,
) -> UserPracticeProfile:
    container = get_container(request)
    try:
        return await container.update_profile_use_case.execute(
            get_user_id(payload),
            body.model_dump(exclude_unset=True),
        )
    except PracticeServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error_code": exc.error_code}) from exc
