import logging
from collections.abc import Callable
from datetime import datetime
from uuid import UUID, uuid5

from src.domain.entities.interview_connection import InterviewConnection
from src.domain.events.assessment_completed import AssessmentCompleted
from src.domain.interfaces.messaging.assessment_completed_publisher import IAssessmentCompletedPublisher
from src.domain.interfaces.repositories.completion_outbox_repository import ICompletionOutboxRepository

logger = logging.getLogger(__name__)

COMPLETION_NAMESPACE = UUID("8d7b6c5e-3f2a-4e1b-a9c0-4b5d6e7f8a90")


class CompletionPublisher:
    def __init__(
        self,
        outbox: ICompletionOutboxRepository,
        publisher: IAssessmentCompletedPublisher,
        clock: Callable[[], datetime],
    ) -> None:
        self._outbox = outbox
        self._publisher = publisher
        self._clock = clock

    async def publish(self, connection: InterviewConnection, session_id: str) -> None:
        context = connection.context
        event = AssessmentCompleted(
            event_id=uuid5(COMPLETION_NAMESPACE, f"{session_id}/completed"),
            occurred_at=self._clock(),
            correlation_id=uuid5(COMPLETION_NAMESPACE, session_id),
            organization_id=context.organization_id,
            vacancy_id=context.vacancy_id,
            invitation_id=context.invitation_id,
            attempt_id=connection.attempt_id,
            session_id=session_id,
            report_reference=f"interview-report:{session_id}",
            report_version=1,
        )
        try:
            await self._outbox.enqueue(event)
            await self._publisher.publish(event)
            await self._outbox.mark_published(event.event_id)
        except Exception:
            logger.exception("Publishing AssessmentCompleted failed for session %s", session_id)
