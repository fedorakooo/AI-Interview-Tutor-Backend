from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class ResetPasswordMessage:
    id: str
    user_id: UUID
    email_address: str
    subject: str
    body: str
    published_at: datetime
    sent_at: datetime | None
