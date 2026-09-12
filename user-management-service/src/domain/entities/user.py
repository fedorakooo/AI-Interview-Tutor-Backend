from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.domain.value_objects.user_role import UserRole


@dataclass
class User:
    id: UUID
    first_name: str
    second_name: str
    username: str
    phone_number: str
    email: str
    hashed_password: str
    role: UserRole
    is_blocked: bool
    created_at: datetime
    modified_at: datetime
    is_email_verified: bool = False
    subscription_tier: str = "free"
    mfa_secret: str | None = None
