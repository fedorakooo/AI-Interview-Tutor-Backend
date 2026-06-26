from dataclasses import dataclass
from uuid import UUID


@dataclass
class UserProfile:
    id: UUID
