from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from jwt_handler.value_objects import AccessTokenPayload
from pydantic import BaseModel, Field
from shared_models.practice.exercise import ExerciseType
from shared_models.practice.messaging import PlanGenerationRequest
from shared_models.practice.plan import PlanStatus
from shared_models.practice.profile import DifficultyLevel
from src.api.security import require_authenticated
from src.app.container import get_container, get_user_id
from src.domain.exceptions.practice_errors import PracticeServiceError

router = APIRouter(prefix="/practice", tags=["Practice Plans"])


class CreatePlanRequest(BaseModel):
    focus_skills: list[str] = Field(default_factory=list)
    difficulty: DifficultyLevel | None = None
    exercise_types: list[ExerciseType] = Field(default_factory=list)
    exercise_count: int = 8
    include_interview_context: bool = True
    include_cv_context: bool = True
    title_hint: str | None = None


class PlanCreatedResponse(BaseModel):
    plan_id: UUID
    status: PlanStatus
    message: str = "Practice plan generation started"


class PlanSummary(BaseModel):
    plan_id: UUID
    status: PlanStatus
    title: str
    focus_skills: list[str]
    difficulty: str
    exercise_count: int
    source: str
    created_at: str
    updated_at: str
    ready_at: str | None = None


@router.post("/plans", status_code=status.HTTP_202_ACCEPTED, response_model=PlanCreatedResponse)
async def create_plan(
    body: CreatePlanRequest,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    request: Request,
) -> PlanCreatedResponse:
    container = get_container(request)
    plan_request = PlanGenerationRequest(
        focus_skills=body.focus_skills,
        difficulty=body.difficulty or DifficultyLevel.MID,
        exercise_types=body.exercise_types,
        exercise_count=body.exercise_count,
        include_interview_context=body.include_interview_context,
        include_cv_context=body.include_cv_context,
        title_hint=body.title_hint,
    )
    try:
        plan = await container.request_plan_use_case.execute(get_user_id(payload), plan_request)
    except PracticeServiceError as exc:
        status_code = (
            status.HTTP_429_TOO_MANY_REQUESTS
            if exc.error_code == "DAILY_PLAN_QUOTA_EXCEEDED"
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(
            status_code=status_code, detail={"error_code": exc.error_code, "message": str(exc)}
        ) from exc
    return PlanCreatedResponse(plan_id=plan.plan_id, status=plan.status)


@router.get("/plans", response_model=list[PlanSummary])
async def list_plans(
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    request: Request,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=50),
    plan_status: PlanStatus | None = Query(default=None, alias="status"),
) -> list[PlanSummary]:
    container = get_container(request)
    plans = await container.list_plans_use_case.execute(
        get_user_id(payload),
        skip=skip,
        limit=limit,
        status=plan_status,
    )
    return [
        PlanSummary(
            plan_id=plan.plan_id,
            status=plan.status,
            title=plan.title,
            focus_skills=plan.focus_skills,
            difficulty=plan.difficulty.value,
            exercise_count=plan.exercise_count,
            source=plan.source.value,
            created_at=plan.created_at.isoformat(),
            updated_at=plan.updated_at.isoformat(),
            ready_at=plan.ready_at.isoformat() if plan.ready_at else None,
        )
        for plan in plans
    ]


@router.get("/plans/{plan_id}")
async def get_plan(
    plan_id: UUID,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    request: Request,
):
    container = get_container(request)
    plan = await container.get_plan_use_case.execute(get_user_id(payload), plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    if plan.status in {PlanStatus.PENDING, PlanStatus.GENERATING}:
        return {
            "plan_id": str(plan.plan_id),
            "status": plan.status.value,
            "message": "Plan is being generated",
        }
    return plan.model_dump(mode="json")


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_plan(
    plan_id: UUID,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    request: Request,
) -> Response:
    container = get_container(request)
    archived = await container.archive_plan_use_case.execute(get_user_id(payload), plan_id)
    if not archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
