"""Publish completion notifications from the durable assessment outbox."""

import asyncio
import logging
import json

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings
from src.infrastructure.postgres.repositories.assessment_repository import AssessmentPostgresRepository
from src.infrastructure.postgres.repositories.organization_repository import OrganizationPostgresRepository
from src.infrastructure.postgres.repositories.user_cv_upload_repository import UserCVUploadPostgresRepository
from src.infrastructure.postgres.repositories.user_repository import UserPostgresRepository
from src.infrastructure.postgres.repositories.vacancy_repository import VacancyPostgresRepository
from src.infrastructure.postgres.uow import SqlAlchemyUnitOfWork
from src.infrastructure.rabbitmq.rabbitmq_producer import RabbitMQProducer


class AssessmentOutboxDispatcher:
    """At-least-once dispatcher; consumers must deduplicate by ``event_id``."""

    def __init__(self, logger: logging.Logger, poll_interval_seconds: float = 1.0):
        self.logger = logger
        self._poll_interval_seconds = poll_interval_seconds
        self._task: asyncio.Task | None = None
        self._engine = create_async_engine(settings.postgres_settings.url)
        self._session_factory = async_sessionmaker(bind=self._engine, expire_on_commit=False)
        self._producer = RabbitMQProducer(
            amqp_url=settings.rabbitmq_settings.url,
            queue_name=settings.rabbitmq_settings.employer_notification_queue_name,
        )

    def _uow(self, session: AsyncSession) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(
            session=session,
            user_repository=UserPostgresRepository(session),
            user_cv_upload_repository=UserCVUploadPostgresRepository(session),
            organization_repository=OrganizationPostgresRepository(session),
            vacancy_repository=VacancyPostgresRepository(session),
            assessment_repository=AssessmentPostgresRepository(session),
        )

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._engine.dispose()

    async def _run(self) -> None:
        while True:
            try:
                await self.dispatch_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                # Payloads may carry business identifiers; avoid dumping them
                # into logs while the row remains retryable in PostgreSQL.
                self.logger.exception("Assessment outbox dispatch failed")
            await asyncio.sleep(self._poll_interval_seconds)

    async def dispatch_once(self) -> int:
        async with self._session_factory() as session:
            uow = self._uow(session)
            async with uow:
                messages = await uow.assessment_repository.claim_outbox_messages(limit=20)

        for message in messages:
            try:
                await self._producer.send_message(json.dumps(message.payload, separators=(",", ":")))
            except Exception as exc:
                async with self._session_factory() as session:
                    uow = self._uow(session)
                    async with uow:
                        await uow.assessment_repository.release_outbox_message(message.id, type(exc).__name__)
                continue
            async with self._session_factory() as session:
                uow = self._uow(session)
                async with uow:
                    await uow.assessment_repository.mark_outbox_published(message.id)
        return len(messages)
