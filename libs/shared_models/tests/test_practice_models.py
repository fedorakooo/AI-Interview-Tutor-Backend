from datetime import UTC, datetime
from uuid import uuid4

from shared_models.practice.exercise import ExerciseType
from shared_models.practice.messaging import (
    InterviewCompletedEvent,
    PlanGenerationRequest,
    PracticePlanJobMessage,
)
from shared_models.practice.plan import PlanSource
from shared_models.practice.profile import DifficultyLevel


class TestPracticePlanJobMessage:
    def test_json_round_trip(self) -> None:
        original = PracticePlanJobMessage(
            job_id=uuid4(),
            plan_id=uuid4(),
            user_id=uuid4(),
            source=PlanSource.COMBINED,
            request=PlanGenerationRequest(
                focus_skills=["PostgreSQL"],
                difficulty=DifficultyLevel.MID,
                exercise_types=[ExerciseType.MCQ_SINGLE, ExerciseType.FLASHCARD],
                exercise_count=8,
            ),
            interview_session_id="session-abc",
            cv_correlation_id=str(uuid4()),
            published_at=datetime.now(UTC),
        )
        restored = PracticePlanJobMessage.model_validate_json(original.model_dump_json())
        assert restored == original


class TestInterviewCompletedEvent:
    def test_json_round_trip(self) -> None:
        original = InterviewCompletedEvent(
            event_id=uuid4(),
            user_id=uuid4(),
            session_id="session-abc-123",
            cv_correlation_id=str(uuid4()),
            published_at=datetime.now(UTC),
        )
        restored = InterviewCompletedEvent.model_validate_json(original.model_dump_json())
        assert restored.session_id == "session-abc-123"


class TestExerciseType:
    def test_enum_values(self) -> None:
        assert ExerciseType.MCQ_SINGLE.value == "mcq_single"
        assert ExerciseType.FLASHCARD.value == "flashcard"
