from datetime import UTC, date, datetime
from uuid import UUID

import pytest
from shared_models.practice.messaging import PracticePlanJobMessage
from shared_models.practice.plan import PlanStatus
from shared_models.practice.profile import UserPracticeProfile
from src.config import settings


@pytest.mark.asyncio
async def test_plan_generation_flow(practice_test_env, access_token):
    env = practice_test_env
    client = env["client"]

    response = await client.post(
        "/api/v1/practice/plans",
        json={"exercise_count": 3},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == PlanStatus.PENDING.value
    plan_id = body["plan_id"]

    published = env["mock_publisher"].published
    assert len(published) == 1
    queue_name, message_json = published[0]
    assert queue_name == settings.rabbitmq_settings.practice_plan_queue_name
    job = PracticePlanJobMessage.model_validate_json(message_json)

    await env["generate_plan_use_case"].execute(job)

    get_response = await client.get(
        f"/api/v1/practice/plans/{plan_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert get_response.status_code == 200
    plan_body = get_response.json()
    assert plan_body["status"] == PlanStatus.READY.value
    assert len(plan_body["exercises"]) == 3

    for exercise in plan_body["exercises"]:
        assert exercise.get("reference_answer") is None
        if exercise["type"] in {"mcq_single", "mcq_multi"}:
            for choice in exercise.get("choices") or []:
                assert choice.get("is_correct") is not True

    mcq_response = await client.post(
        f"/api/v1/practice/plans/{plan_id}/exercises/mcq-1/attempt",
        json={"selected_choice_ids": ["a"]},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert mcq_response.status_code == 200
    mcq_body = mcq_response.json()
    assert mcq_body["grading"]["score"] == 10.0
    assert mcq_body["grading"]["is_correct"] is True

    wrong_mcq = await client.post(
        f"/api/v1/practice/plans/{plan_id}/exercises/mcq-1/attempt",
        json={"selected_choice_ids": ["b"]},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert wrong_mcq.status_code == 409
    assert wrong_mcq.json()["detail"]["error_code"] == "ALREADY_ATTEMPTED"

    open_response = await client.post(
        f"/api/v1/practice/plans/{plan_id}/exercises/open-1/attempt",
        json={"text_answer": "REST uses HTTP resources"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert open_response.status_code == 200
    open_body = open_response.json()
    assert open_body["grading"]["score"] == 8.0
    assert open_body["grading"]["graded_by"] == "llm"
    assert open_body["reference_answer"] == "Representational state transfer"
    env["mock_answer_grader"].grade_open_question.assert_awaited()


@pytest.mark.asyncio
async def test_cross_user_access_returns_404(practice_test_env, access_token, other_access_token):
    env = practice_test_env
    client = env["client"]

    create_response = await client.post(
        "/api/v1/practice/plans",
        json={"exercise_count": 3},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    plan_id = create_response.json()["plan_id"]

    other_response = await client.get(
        f"/api/v1/practice/plans/{plan_id}",
        headers={"Authorization": f"Bearer {other_access_token}"},
    )
    assert other_response.status_code == 404


@pytest.mark.asyncio
async def test_daily_plan_quota_exceeded(practice_test_env, access_token, user_id):
    env = practice_test_env
    client = env["client"]
    profile_repo = env["profile_repository"]

    profile = UserPracticeProfile(
        user_id=UUID(user_id),
        daily_plan_quota=1,
        plans_generated_today=1,
        quota_reset_date=date.today(),
        updated_at=datetime.now(UTC),
    )
    await profile_repo.upsert_profile(profile)

    response = await client.post(
        "/api/v1/practice/plans",
        json={"exercise_count": 3},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 429
    detail = response.json()["detail"]
    assert detail["error_code"] == "DAILY_PLAN_QUOTA_EXCEEDED"
