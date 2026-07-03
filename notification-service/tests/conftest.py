from datetime import UTC, datetime
from uuid import uuid4

import pytest


@pytest.fixture
def sample_reset_password_payload() -> dict:
    return {
        "user_id": str(uuid4()),
        "email": "user@example.com",
        "subject": "Password Reset Request",
        "body": "Click the link to reset your password",
        "published_at": datetime.now(UTC).isoformat(),
    }
