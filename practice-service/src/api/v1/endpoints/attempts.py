from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jwt_handler.value_objects import AccessTokenPayload
from pydantic import BaseModel
from shared_models.practice.attempt import AttemptStatus, ExerciseAttempt, GradingResult
from shared_models.practice.exercise import FlashcardRating
from src.api.security import require_authenticated
from src.app.container import get_container, get_user_id
from src.domain.exceptions.practice_errors import PracticeServiceError

router = APIRouter(prefix="/practice", tags=["Practice Attempts"])


class AttemptRequest(BaseModel):
    selected_choice_ids: list[str] | None = None
    text_answer: str | None = None
    flashcard_rating: FlashcardRating | None = None
    revealed_back: bool | None = None


class AttemptResponse(BaseModel):
    attempt_id: UUID
    status: AttemptStatus
    grading: GradingResult | None = None
    reference_answer: str | None = None
    explanation: str | None = None


@router.post(
    "/plans/{plan_id}/exercises/{exercise_id}/attempt",
    response_model=AttemptResponse,
)
async def submit_attempt(
    plan_id: UUID,
    exercise_id: str,
    body: AttemptRequest,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    request: Request,
) -> AttemptResponse:
    container = get_container(request)
    answer_payload = body.model_dump(exclude_none=True)
    try:
        attempt, reference_answer, explanation = await container.submit_attempt_use_case.execute(
            get_user_id(payload),
            plan_id,
            exercise_id,
            answer_payload,
        )
    except PracticeServiceError as exc:
        status_code = status.HTTP_404_NOT_FOUND
        if exc.error_code == "PLAN_NOT_READY":
            status_code = status.HTTP_409_CONFLICT
        elif exc.error_code == "ALREADY_ATTEMPTED":
            status_code = status.HTTP_409_CONFLICT
        elif exc.error_code in {"INVALID_ANSWER_FORMAT", "ANSWER_TOO_LONG"}:
            status_code = status.HTTP_400_BAD_REQUEST
        elif exc.error_code == "GRADING_FAILED":
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        raise HTTPException(
            status_code=status_code, detail={"error_code": exc.error_code, "message": str(exc)}
        ) from exc

    return AttemptResponse(
        attempt_id=attempt.attempt_id,
        status=attempt.status,
        grading=attempt.grading,
        reference_answer=reference_answer,
        explanation=explanation,
    )


@router.get("/plans/{plan_id}/progress")
async def get_progress(
    plan_id: UUID,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    request: Request,
) -> dict[str, Any]:
    container = get_container(request)
    progress = await container.get_progress_use_case.execute(get_user_id(payload), plan_id)
    if progress is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return progress


@router.get(
    "/plans/{plan_id}/exercises/{exercise_id}/attempts",
    response_model=list[ExerciseAttempt],
)
async def list_attempts(
    plan_id: UUID,
    exercise_id: str,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    request: Request,
) -> list[ExerciseAttempt]:
    container = get_container(request)
    plan = await container.get_plan_use_case.execute(get_user_id(payload), plan_id, sanitize=False)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    attempts = await container.attempt_repository.list_attempts(
        str(get_user_id(payload)),
        str(plan_id),
        exercise_id,
    )
    return attempts
