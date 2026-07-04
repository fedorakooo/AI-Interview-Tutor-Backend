import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared_models.interview.report import InterviewReport, SkillScore
from shared_models.interview.session import InterviewSessionDocument, InterviewSessionStatus
from src.infrastructure.redis.session_registry import RedisSessionRegistry


@pytest.mark.asyncio
async def test_session_registry_register_and_get():
    redis = AsyncMock()
    pipe = MagicMock()
    redis.pipeline = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[True, 1, 1])
    redis.get = AsyncMock(
        return_value=json.dumps(
            {
                "session_id": "session-1",
                "user_id": "user-1",
                "instance_id": "instance-1",
                "status": InterviewSessionStatus.ACTIVE.value,
                "started_at": datetime.now(UTC).isoformat(),
            }
        )
    )

    registry = RedisSessionRegistry(redis, instance_id="instance-1")
    await registry.register_session("session-1", "user-1")

    entry = await registry.get_session("session-1")
    assert entry is not None
    assert entry.session_id == "session-1"
    assert entry.user_id == "user-1"


def test_interview_report_model():
    report = InterviewReport(
        summary="Strong candidate",
        skill_scores=[SkillScore(skill="Python", score=8.5, notes="Solid answers")],
        strengths=["Communication"],
        weaknesses=["System design depth"],
        recommendations=["Practice architecture questions"],
    )
    assert report.skill_scores[0].skill == "Python"


def test_interview_session_document_roundtrip():
    document = InterviewSessionDocument(
        session_id="session-1",
        user_id="user-1",
        status=InterviewSessionStatus.COMPLETED,
        started_at=datetime.now(UTC),
        overall_stage="Completed",
        message_count=12,
        report=InterviewReport(summary="Done"),
    )
    restored = InterviewSessionDocument.from_mongo(document.to_mongo())
    assert restored.session_id == "session-1"
    assert restored.status == InterviewSessionStatus.COMPLETED
