from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class CVInitialAnalysisMessage(BaseModel):
    user_id: UUID
    subject: str
    url: str
    published_at: datetime

    def model_dump(self, **kwargs) -> dict[str, Any]:
        data = super().model_dump()
        data["user_id"] = str(data["user_id"])
        return data


class CVResultAnalysisMessage(BaseModel):
    user_id: UUID
    subject: str
    url: str
    body: str
    published_at: datetime

    def model_dump(self, **kwargs) -> dict[str, Any]:
        data = super().model_dump(**kwargs)
        data["user_id"] = str(data["user_id"])
        data["published_at"] = data["published_at"].isoformat()
        return data
