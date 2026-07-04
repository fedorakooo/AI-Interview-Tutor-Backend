from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

from shared_models.interview.report import InterviewReport


class InterviewSessionStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    SUSPENDED = "suspended"
    FAILED = "failed"


class InterviewSessionDocument(BaseModel):
    session_id: str
    user_id: str
    status: InterviewSessionStatus
    started_at: datetime
    completed_at: datetime | None = None
    overall_stage: str
    message_count: int = 0
    report: InterviewReport | None = None
    cv_correlation_id: str | None = None
    instance_id: str | None = None

    def to_mongo(self) -> dict:
        data = self.model_dump(mode="json")
        data["status"] = self.status.value
        return data

    @classmethod
    def from_mongo(cls, data: dict) -> "InterviewSessionDocument":
        payload = dict(data)
        payload.pop("_id", None)
        if isinstance(payload.get("status"), str):
            payload["status"] = InterviewSessionStatus(payload["status"])
        return cls.model_validate(payload)


InterviewSessionStatusLiteral = Literal["active", "completed", "suspended", "failed"]
