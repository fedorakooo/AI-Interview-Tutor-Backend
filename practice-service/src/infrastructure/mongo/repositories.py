from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from pymongo import ReturnDocument
from shared_models.practice.plan import PlanStatus, PracticePlan
from shared_models.practice.profile import DifficultyLevel, UserPracticeProfile
from src.config import settings
from src.infrastructure.mongo.client import MongoClientFactory


class PlanRepository:
    def __init__(self, mongo_client) -> None:
        self._collection = MongoClientFactory.get_collection(
            mongo_client,
            settings.mongo_settings.db_name,
            settings.mongo_settings.practice_plans_collection_name,
        )

    async def ensure_indexes(self) -> None:
        await self._collection.create_index("plan_id", unique=True)
        await self._collection.create_index([("user_id", 1), ("created_at", -1)])
        await self._collection.create_index([("user_id", 1), ("status", 1)])
        await self._collection.create_index(
            "interview_session_id",
            unique=True,
            partialFilterExpression={"interview_session_id": {"$type": "string"}},
        )

    async def create_plan(self, plan: PracticePlan) -> PracticePlan:
        await self._collection.insert_one(self._to_document(plan))
        return plan

    async def get_plan(self, plan_id: str, user_id: str) -> PracticePlan | None:
        document = await self._collection.find_one({"plan_id": plan_id, "user_id": user_id})
        return self._from_document(document) if document else None

    async def get_plan_by_id(self, plan_id: str) -> PracticePlan | None:
        document = await self._collection.find_one({"plan_id": plan_id})
        return self._from_document(document) if document else None

    async def get_plan_by_interview_session(self, interview_session_id: str) -> PracticePlan | None:
        document = await self._collection.find_one({"interview_session_id": interview_session_id})
        return self._from_document(document) if document else None

    async def update_plan(self, plan_id: str, update_data: dict[str, Any]) -> bool:
        result = await self._collection.update_one({"plan_id": plan_id}, {"$set": update_data})
        return result.modified_count > 0 or result.matched_count > 0

    async def try_claim_plan_generation(self, plan_id: str) -> PracticePlan | None:
        now = datetime.now(UTC)
        document = await self._collection.find_one_and_update(
            {"plan_id": plan_id, "status": PlanStatus.PENDING.value},
            {"$set": {"status": PlanStatus.GENERATING.value, "updated_at": now.isoformat()}},
            return_document=ReturnDocument.AFTER,
        )
        return self._from_document(document) if document else None

    async def list_plans(
        self,
        user_id: str,
        *,
        skip: int = 0,
        limit: int = 20,
        status: PlanStatus | None = None,
    ) -> list[PracticePlan]:
        query: dict[str, Any] = {"user_id": user_id}
        if status is not None:
            query["status"] = status.value
        cursor = self._collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        documents = await cursor.to_list(length=limit)
        return [self._from_document(document) for document in documents]

    @staticmethod
    def _to_document(plan: PracticePlan) -> dict[str, Any]:
        document = plan.model_dump(mode="json")
        document["plan_id"] = str(plan.plan_id)
        document["user_id"] = str(plan.user_id)
        return document

    @staticmethod
    def _from_document(document: dict[str, Any]) -> PracticePlan:
        payload = dict(document)
        payload.pop("_id", None)
        return PracticePlan.model_validate(payload)


class AttemptRepository:
    def __init__(self, mongo_client) -> None:
        self._collection = MongoClientFactory.get_collection(
            mongo_client,
            settings.mongo_settings.db_name,
            settings.mongo_settings.practice_attempts_collection_name,
        )

    async def ensure_indexes(self) -> None:
        await self._collection.create_index(
            [("user_id", 1), ("plan_id", 1), ("exercise_id", 1)],
            unique=True,
        )
        await self._collection.create_index([("user_id", 1), ("submitted_at", -1)])
        await self._collection.create_index("plan_id")

    async def upsert_attempt(self, attempt) -> Any:
        document = attempt.model_dump(mode="json")
        document["attempt_id"] = str(attempt.attempt_id)
        document["plan_id"] = str(attempt.plan_id)
        document["user_id"] = str(attempt.user_id)
        await self._collection.update_one(
            {
                "user_id": str(attempt.user_id),
                "plan_id": str(attempt.plan_id),
                "exercise_id": attempt.exercise_id,
            },
            {"$set": document},
            upsert=True,
        )
        return attempt

    async def get_attempt(self, user_id: str, plan_id: str, exercise_id: str):
        from shared_models.practice.attempt import ExerciseAttempt

        document = await self._collection.find_one({"user_id": user_id, "plan_id": plan_id, "exercise_id": exercise_id})
        return ExerciseAttempt.model_validate(document) if document else None

    async def list_attempts(self, user_id: str, plan_id: str, exercise_id: str):
        from shared_models.practice.attempt import ExerciseAttempt

        cursor = self._collection.find({"user_id": user_id, "plan_id": plan_id, "exercise_id": exercise_id})
        documents = await cursor.to_list(length=100)
        return [ExerciseAttempt.model_validate(document) for document in documents]

    async def list_plan_attempts(self, user_id: str, plan_id: str):
        from shared_models.practice.attempt import ExerciseAttempt

        cursor = self._collection.find({"user_id": user_id, "plan_id": plan_id})
        documents = await cursor.to_list(length=100)
        return [ExerciseAttempt.model_validate(document) for document in documents]


class ProfileRepository:
    def __init__(self, mongo_client) -> None:
        self._collection = MongoClientFactory.get_collection(
            mongo_client,
            settings.mongo_settings.db_name,
            settings.mongo_settings.user_practice_profiles_collection_name,
        )

    async def ensure_indexes(self) -> None:
        await self._collection.create_index("user_id", unique=True)

    async def get_profile(self, user_id: str) -> UserPracticeProfile | None:
        document = await self._collection.find_one({"user_id": user_id})
        return UserPracticeProfile.model_validate(document) if document else None

    async def upsert_profile(self, profile: UserPracticeProfile) -> UserPracticeProfile:
        document = profile.model_dump(mode="json")
        document["user_id"] = str(profile.user_id)
        await self._collection.update_one({"user_id": str(profile.user_id)}, {"$set": document}, upsert=True)
        return profile

    @staticmethod
    def default_profile(user_id: UUID) -> UserPracticeProfile:
        from shared_models.practice.exercise import ExerciseType

        return UserPracticeProfile(
            user_id=user_id,
            preferred_difficulty=DifficultyLevel.MID,
            preferred_exercise_types=[
                ExerciseType.MCQ_SINGLE,
                ExerciseType.OPEN_QUESTION,
                ExerciseType.FLASHCARD,
            ],
            daily_plan_quota=settings.practice_settings.default_daily_plan_quota,
            updated_at=datetime.now(UTC),
        )

    async def reset_quota_if_needed(self, profile: UserPracticeProfile) -> UserPracticeProfile:
        today = date.today()
        if profile.quota_reset_date != today:
            profile.plans_generated_today = 0
            profile.quota_reset_date = today
            profile.updated_at = datetime.now(UTC)
            await self.upsert_profile(profile)
        return profile
