import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from uuid import UUID, uuid4

from src.domain.exceptions.not_found_error import NotFoundError
from src.domain.interfaces.database.uow import IUnitOfWork
from src.domain.interfaces.reports.interview_data_eraser import IInterviewDataEraser
from src.domain.interfaces.storage.s3_client import IS3Client
from src.infrastructure.postgres.schemas.assessment_flow import AuditLogORM

ERASED_EMAIL_DOMAIN = "erased.invalid"
ERASED_OBJECT_KEY = "erased"

UowFactory = Callable[[], AbstractAsyncContextManager[IUnitOfWork]]


def erased_email(record_id: UUID) -> str:
    return f"{record_id}@{ERASED_EMAIL_DOMAIN}"


def is_erased(email: str) -> bool:
    return email.endswith(f"@{ERASED_EMAIL_DOMAIN}")


class EraseAttemptDataUseCase:
    def __init__(self, uow: IUnitOfWork, eraser: IInterviewDataEraser, s3_client: IS3Client):
        self._uow = uow
        self._eraser = eraser
        self._s3 = s3_client

    async def __call__(self, organization_id: UUID, attempt_id: UUID, actor_user_id: UUID | None, reason: str) -> bool:
        """Erase the personal data of one attempt everywhere and report whether anything was erased."""
        async with self._uow:
            repository = self._uow.assessment_repository
            attempt = await repository.get_attempt_for_organization(organization_id, attempt_id)
            if attempt is None:
                raise NotFoundError("Assessment attempt not found")
            if is_erased(attempt.candidate_email_normalized):
                return False
            cv_correlation_id = attempt.cv_correlation_id
            upload = await repository.get_cv_upload_for_attempt(attempt_id)
            object_key = upload.s3_object_key if upload is not None else None

        result = await self._eraser.erase(attempt_id, cv_correlation_id)
        if object_key and object_key != ERASED_OBJECT_KEY:
            await self._s3.delete_object(object_key)

        async with self._uow:
            repository = self._uow.assessment_repository
            row = await repository.get_attempt_with_invitation(attempt_id)
            if row is None:
                raise NotFoundError("Assessment attempt not found")
            attempt, invitation = row
            attempt.candidate_email_normalized = erased_email(attempt.id)
            attempt.candidate_display_name = None
            attempt.report_reference = None
            attempt.interview_session_id = None
            invitation.candidate_email_normalized = erased_email(invitation.id)
            upload = await repository.get_cv_upload_for_attempt(attempt_id)
            if upload is not None:
                upload.s3_object_key = ERASED_OBJECT_KEY
                upload.original_filename = None
                upload.mongo_document_id = None
            await repository.clear_decision_notes(attempt_id)
            await repository.create_audit_entry(
                AuditLogORM(
                    id=uuid4(),
                    actor_type="user" if actor_user_id else "service",
                    actor_id=actor_user_id,
                    action="assessment.data_erased",
                    organization_id=organization_id,
                    vacancy_id=invitation.vacancy_id,
                    invitation_id=invitation.id,
                    attempt_id=attempt_id,
                    after={"reason": reason, "deleted": result.deleted},
                )
            )
            return True


class EraseExpiredInvitationUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def __call__(self, organization_id: UUID, invitation_id: UUID) -> bool:
        async with self._uow:
            repository = self._uow.assessment_repository
            invitation = await repository.get_invitation(organization_id, invitation_id)
            if invitation is None:
                raise NotFoundError("Invitation not found")
            if is_erased(invitation.candidate_email_normalized):
                return False
            invitation.candidate_email_normalized = erased_email(invitation.id)
            await repository.create_audit_entry(
                AuditLogORM(
                    id=uuid4(),
                    actor_type="service",
                    actor_id=None,
                    action="invitation.data_erased",
                    organization_id=organization_id,
                    vacancy_id=invitation.vacancy_id,
                    invitation_id=invitation.id,
                    after={"reason": "retention"},
                )
            )
            return True


class PurgeExpiredAssessmentDataUseCase:
    def __init__(
        self,
        uow_factory: UowFactory,
        eraser: IInterviewDataEraser,
        s3_client: IS3Client,
        logger: logging.Logger,
    ):
        self._uow_factory = uow_factory
        self._eraser = eraser
        self._s3 = s3_client
        self._logger = logger

    async def __call__(self, batch_size: int) -> int:
        """Erase one batch of records older than their organization's retention period."""
        async with self._uow_factory() as uow:
            async with uow:
                attempts = [
                    (invitation.organization_id, attempt.id)
                    for attempt, invitation in await uow.assessment_repository.list_attempts_due_for_erasure(batch_size)
                ]
                invitations = [
                    (invitation.organization_id, invitation.id)
                    for invitation in await uow.assessment_repository.list_invitations_due_for_erasure(batch_size)
                ]

        erased = 0
        for organization_id, attempt_id in attempts:
            try:
                async with self._uow_factory() as uow:
                    if await EraseAttemptDataUseCase(uow, self._eraser, self._s3)(
                        organization_id, attempt_id, None, "retention"
                    ):
                        erased += 1
            except Exception:
                self._logger.exception("Retention erasure of an attempt failed")
        for organization_id, invitation_id in invitations:
            try:
                async with self._uow_factory() as uow:
                    if await EraseExpiredInvitationUseCase(uow)(organization_id, invitation_id):
                        erased += 1
            except Exception:
                self._logger.exception("Retention erasure of an invitation failed")
        return erased
