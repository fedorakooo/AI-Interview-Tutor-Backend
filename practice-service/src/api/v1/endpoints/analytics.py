from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from jwt_handler.value_objects import AccessTokenPayload
from pydantic import BaseModel, Field

from src.api.security import require_authenticated
from src.app.container import get_container, get_user_id

router = APIRouter(prefix="/practice", tags=["Practice Analytics"])



class SkillTrendPoint(BaseModel):
    skill: str
    average_score: float
    attempts: int


class PracticeAnalytics(BaseModel):
    weak_topics: list[str] = Field(default_factory=list)
    skill_trends: list[SkillTrendPoint] = Field(default_factory=list)
    recommended_focus: list[str] = Field(default_factory=list)
    due_flashcards: int = 0


class DueFlashcard(BaseModel):
    plan_id: str
    exercise_id: str
    title: str
    prompt: str
    next_review_at: datetime | None = None


@router.get("/analytics", response_model=PracticeAnalytics)
async def practice_analytics(
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    request: Request,
) -> PracticeAnalytics:
    container = get_container(request)
    user_id = get_user_id(payload)
    plans = await container.list_plans_use_case.execute(user_id, limit=50)
    scores: dict[str, list[float]] = defaultdict(list)
    due = 0
    now = datetime.now(UTC)

    for plan in plans:
        attempts = await container.attempt_repository.list_plan_attempts(str(user_id), str(plan.plan_id))
        exercise_map = {exercise.exercise_id: exercise for exercise in plan.exercises}
        for attempt in attempts:
            if attempt.grading is None:
                continue
            exercise = exercise_map.get(attempt.exercise_id)
            if not exercise:
                continue
            for skill in exercise.skill_tags or ["general"]:
                scores[skill].append(float(attempt.grading.score))
            next_review = attempt.next_review_at
            if next_review and next_review <= now:
                due += 1

    trends = [
        SkillTrendPoint(skill=skill, average_score=round(sum(vals) / len(vals), 2), attempts=len(vals))
        for skill, vals in scores.items()
    ]
    trends.sort(key=lambda item: item.average_score)
    weak = [item.skill for item in trends[:5] if item.average_score < 6.5]
    return PracticeAnalytics(
        weak_topics=weak,
        skill_trends=trends,
        recommended_focus=weak[:3] or [item.skill for item in trends[:3]],
        due_flashcards=due,
    )


@router.get("/due-flashcards", response_model=list[DueFlashcard])
async def due_flashcards(
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    request: Request,
) -> list[DueFlashcard]:
    container = get_container(request)
    user_id = get_user_id(payload)
    plans = await container.list_plans_use_case.execute(user_id, limit=20)
    now = datetime.now(UTC)
    due_items: list[DueFlashcard] = []
    for plan in plans:
        attempts = await container.attempt_repository.list_plan_attempts(str(user_id), str(plan.plan_id))
        latest_by_exercise = {attempt.exercise_id: attempt for attempt in attempts}
        for exercise in plan.exercises:
            if getattr(exercise.type, "value", str(exercise.type)) != "flashcard":
                continue
            attempt = latest_by_exercise.get(exercise.exercise_id)
            next_review = attempt.next_review_at if attempt else now
            if attempt is None or (next_review and next_review <= now):
                due_items.append(
                    DueFlashcard(
                        plan_id=str(plan.plan_id),
                        exercise_id=exercise.exercise_id,
                        title=exercise.title,
                        prompt=exercise.prompt,
                        next_review_at=next_review,
                    )
                )
    return due_items
