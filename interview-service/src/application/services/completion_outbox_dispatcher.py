import asyncio
import logging

from src.domain.interfaces.messaging.assessment_completed_publisher import IAssessmentCompletedPublisher
from src.domain.interfaces.repositories.completion_outbox_repository import ICompletionOutboxRepository

logger = logging.getLogger(__name__)


class CompletionOutboxDispatcher:
    def __init__(
        self,
        outbox: ICompletionOutboxRepository,
        publisher: IAssessmentCompletedPublisher,
        interval_seconds: float = 30.0,
        batch_size: int = 20,
    ) -> None:
        self._outbox = outbox
        self._publisher = publisher
        self._interval_seconds = interval_seconds
        self._batch_size = batch_size
        self._task: asyncio.Task | None = None

    async def dispatch_once(self) -> int:
        published = 0
        for event in await self._outbox.list_pending(self._batch_size):
            try:
                await self._publisher.publish(event)
                await self._outbox.mark_published(event.event_id)
                published += 1
            except Exception:
                logger.exception("Retrying AssessmentCompleted publication failed for event %s", event.event_id)
        return published

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        while True:
            try:
                await self.dispatch_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Completion outbox run failed")
            await asyncio.sleep(self._interval_seconds)
