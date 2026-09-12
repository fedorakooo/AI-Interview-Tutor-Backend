from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


class PracticePlanReadyNotifier:
    """Publishes a notification email payload when a practice plan is ready."""

    def __init__(self, email_producer) -> None:
        self._email_producer = email_producer

    async def notify(self, *, user_id: str, email: str | None, plan_id: str, title: str) -> None:
        if not email:
            logger.info("No email for user %s; skipping plan-ready notification", user_id)
            return
        message = {
            "user_id": user_id,
            "email": email,
            "email_type": "plan_ready",
            "subject": "Your practice plan is ready",
            "body": f"Your practice plan '{title}' ({plan_id}) is ready. Open the Practice section to start.",
            "published_at": datetime.now(UTC).isoformat(),
        }
        await self._email_producer.send_message(json.dumps(message))
        logger.info("Queued plan-ready notification for user %s plan %s", user_id, plan_id)
