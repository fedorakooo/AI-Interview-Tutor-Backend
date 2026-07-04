from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from shared_models.interview.report import InterviewReport, SkillScore
from shared_models.interview.session import InterviewSessionDocument, InterviewSessionStatus
from shared_models.practice.messaging import InterviewCompletedEvent, PracticePlanJobMessage
from shared_models.practice.plan import PlanSource, PlanStatus
from shared_models.practice.profile import UserPracticeProfile
from src.config import settings
from src.infrastructure.mongo.client import MongoClientFactory


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
async def test_interview_auto_plan_idempotency(practice_test_env, user_id):
    env = practice_test_env
    session_id = f"session-{uuid4()}"
    mongo_client = env["mongo_client"]
    sessions = MongoClientFactory.get_collection(
        mongo_client,
        settings.mongo_settings.db_name,
        settings.mongo_settings.interview_sessions_collection_name,
    )
    session_doc = InterviewSessionDocument(
        session_id=session_id,
        user_id=user_id,
        status=InterviewSessionStatus.COMPLETED,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        overall_stage="completed",
        report=InterviewReport(
            summary="Done",
            weaknesses=["Caching"],
            skill_scores=[SkillScore(skill="Redis", score=4.0)],
        ),
    )
    await sessions.insert_one(session_doc.to_mongo())

    event = InterviewCompletedEvent(
        event_id=uuid4(),
        user_id=UUID(user_id),
        session_id=session_id,
        published_at=datetime.now(UTC),
    )

    first = await env["handle_interview_use_case"].execute(event)
    assert first is True

    plan = await env["plan_repository"].get_plan_by_interview_session(session_id)
    assert plan is not None
    assert plan.source == PlanSource.INTERVIEW
    assert plan.interview_session_id == session_id

    second = await env["handle_interview_use_case"].execute(event)
    assert second is False

    plans = await env["plan_repository"].list_plans(user_id)
    interview_plans = [p for p in plans if p.interview_session_id == session_id]
    assert len(interview_plans) == 1


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
