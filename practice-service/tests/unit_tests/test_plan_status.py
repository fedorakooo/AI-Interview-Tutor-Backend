from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from shared_models.practice.plan import PlanStatus
from src.application.use_cases.plan_use_cases import GetPlanStatusUseCase
from src.infrastructure.mongo.repositories import PlanStatusSnapshot


@pytest.mark.asyncio
async def test_get_plan_status_use_case_returns_snapshot() -> None:
    plan_id = uuid4()
    user_id = uuid4()
    snapshot = PlanStatusSnapshot(
        plan_id=plan_id,
        status=PlanStatus.GENERATING,
        ready_at=None,
        error_code=None,
        error_message=None,
    )
    plan_repo = AsyncMock()
    plan_repo.get_plan_status = AsyncMock(return_value=snapshot)

    result = await GetPlanStatusUseCase(plan_repo).execute(user_id, plan_id)

    assert result is snapshot
    plan_repo.get_plan_status.assert_awaited_once_with(str(plan_id), str(user_id))
    plan_repo.get_plan.assert_not_called()


@pytest.mark.asyncio
async def test_get_plan_status_use_case_returns_none_when_missing() -> None:
    plan_repo = AsyncMock()
    plan_repo.get_plan_status = AsyncMock(return_value=None)

    result = await GetPlanStatusUseCase(plan_repo).execute(uuid4(), uuid4())

    assert result is None


@pytest.mark.asyncio
async def test_plan_repository_get_plan_status_uses_projection() -> None:
    plan_id = uuid4()
    user_id = uuid4()
    collection = AsyncMock()
    collection.find_one = AsyncMock(
        return_value={
            "plan_id": str(plan_id),
            "status": PlanStatus.READY.value,
            "ready_at": datetime.now(UTC).isoformat(),
            "error_code": None,
            "error_message": None,
        }
    )

    from src.infrastructure.mongo.repositories import PlanRepository

    repo = PlanRepository.__new__(PlanRepository)
    repo._collection = collection

    snapshot = await repo.get_plan_status(str(plan_id), str(user_id))

    assert snapshot is not None
    assert snapshot.plan_id == plan_id
    assert snapshot.status == PlanStatus.READY
    kwargs = collection.find_one.await_args.kwargs
    assert "projection" in kwargs
    assert kwargs["projection"]["plan_id"] == 1
    assert "exercises" not in kwargs["projection"]
