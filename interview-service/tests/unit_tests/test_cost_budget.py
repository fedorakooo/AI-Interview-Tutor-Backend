from src.infrastructure.redis.cost_budget import CostBudgetTracker


import pytest


@pytest.mark.asyncio
async def test_cost_budget_without_redis():
    tracker = CostBudgetTracker(redis_client=None, daily_token_cap=100)
    assert await tracker.get_usage("user-1") == 0
    assert await tracker.is_over_budget("user-1") is False
