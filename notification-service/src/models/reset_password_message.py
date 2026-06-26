from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ResetPasswordMessageModel(BaseModel):
    user_id: UUID
    email: str
    subject: str
    body: str
    published_at: datetime

    def model_dump(self, **kwargs):
        data = super().model_dump(**kwargs)
        data["user_id"] = str(data["user_id"])
        return data
