"""Consume authoritative Interview Service assessment completion events."""

import asyncio
import logging

import aio_pika
from shared_models.assessment.contracts import AssessmentCompleted
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.application.use_cases.assessments import RegisterAssessmentCompletionUseCase
from src.config import settings
from src.infrastructure.postgres.repositories.assessment_repository import AssessmentPostgresRepository
from src.infrastructure.postgres.repositories.organization_repository import OrganizationPostgresRepository
from src.infrastructure.postgres.repositories.user_cv_upload_repository import UserCVUploadPostgresRepository
from src.infrastructure.postgres.repositories.user_repository import UserPostgresRepository
from src.infrastructure.postgres.repositories.vacancy_repository import VacancyPostgresRepository
from src.infrastructure.postgres.uow import SqlAlchemyUnitOfWork


class AssessmentCompletedConsumer:
    """Durable, idempotent consumer for the one trusted report write-path."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self._task: asyncio.Task | None = None
        self._engine = create_async_engine(settings.postgres_settings.url)
        self._session_factory = async_sessionmaker(bind=self._engine, expire_on_commit=False)

    async def start(self) -> None:
        self._task = asyncio.create_task(self._consume_loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._engine.dispose()

    async def _consume_loop(self) -> None:
        connection = await aio_pika.connect_robust(settings.rabbitmq_settings.url)
        async with connection:
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=5)
            queue = await channel.declare_queue(
                settings.rabbitmq_settings.assessment_completed_queue_name,
                durable=True,
            )
            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        await self._handle_message(message.body.decode())

    async def _handle_message(self, payload: str) -> None:
        event = AssessmentCompleted.model_validate_json(payload)
        async with self._session_factory() as session:
            uow = SqlAlchemyUnitOfWork(
                session=session,
                user_repository=UserPostgresRepository(session),
                user_cv_upload_repository=UserCVUploadPostgresRepository(session),
                organization_repository=OrganizationPostgresRepository(session),
                vacancy_repository=VacancyPostgresRepository(session),
                assessment_repository=AssessmentPostgresRepository(session),
            )
            completed = await RegisterAssessmentCompletionUseCase(uow)(event)
        if completed is None:
            self.logger.info("Ignored duplicate assessment completion event_id=%s", event.event_id)
        else:
            self.logger.info("Registered assessment completion attempt_id=%s", event.attempt_id)
