from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from shared_models.assessment.contracts import AttemptStatus, InvitationStatus, VacancyStatus
from shared_models.messaging.common import AnalysisStatus
from shared_models.messaging.cv_analysis import CVAnalysisJobMessage

from src.config import settings
from src.domain.exceptions.not_found_error import NotFoundError
from src.domain.interfaces.database.uow import IUnitOfWork
from src.infrastructure.postgres.schemas.assessment_flow import CandidateAttemptORM, CandidateInvitationORM
from src.infrastructure.postgres.schemas.assessment_flow import AuditLogORM
from src.infrastructure.postgres.schemas.assessment_flow import AssessmentCVUploadORM


class AssessmentFlowError(Exception):
    """A deliberately non-specific public-flow failure."""


def utcnow() -> datetime:
    return datetime.now(UTC)


class CreateInvitationUseCase:
    def __init__(self, uow: IUnitOfWork, token_handler):
        self._uow, self._tokens = uow, token_handler

    async def __call__(self, organization_id: UUID, vacancy_id: UUID, actor_user_id: UUID, email: str) -> tuple[CandidateInvitationORM, str]:
        normalized_email = email.strip().casefold()
        async with self._uow:
            vacancy = await self._uow.vacancy_repository.get_by_id_and_organization_id(vacancy_id, organization_id)
            if vacancy is None or vacancy.status != VacancyStatus.ACTIVE or vacancy.active_template_version is None:
                raise NotFoundError("Active vacancy not found")
            template = await self._uow.vacancy_repository.get_template(vacancy_id, vacancy.active_template_version)
            if template is None:
                raise NotFoundError("Active template not found")
            token = self._tokens.generate()
            invitation = CandidateInvitationORM(
                id=uuid4(), organization_id=organization_id, vacancy_id=vacancy_id,
                template_id=template.id, template_version=template.version,
                token_hash=self._tokens.hash(token), candidate_email_normalized=normalized_email,
                expires_at=utcnow() + timedelta(hours=settings.assessment_settings.invitation_ttl_hours),
                max_attempts=1, attempts_started=0, status=InvitationStatus.CREATED.value, created_by=actor_user_id,
            )
            invitation = await self._uow.assessment_repository.create_invitation(invitation)
            await self._uow.assessment_repository.create_audit_entry(
                AuditLogORM(
                    id=uuid4(), actor_type="user", actor_id=actor_user_id,
                    action="invitation.issued", organization_id=organization_id,
                    vacancy_id=vacancy_id, invitation_id=invitation.id,
                    # Do not store a raw link, token, or candidate email in audit data.
                    after={"template_version": template.version, "expires_at": invitation.expires_at.isoformat()},
                )
            )
            return invitation, token


class PublicInvitationUseCase:
    def __init__(self, uow: IUnitOfWork, token_handler):
        self._uow, self._tokens = uow, token_handler

    async def preflight(self, token: str) -> CandidateInvitationORM:
        unavailable = False
        async with self._uow:
            invitation = await self._uow.assessment_repository.get_invitation_by_hash_for_update(self._tokens.hash(token))
            if invitation is None or invitation.status in {InvitationStatus.REVOKED.value, InvitationStatus.COMPLETED.value}:
                unavailable = True
            elif invitation.expires_at <= utcnow():
                invitation.status = InvitationStatus.EXPIRED.value
                unavailable = True
            elif invitation.status == InvitationStatus.CREATED.value:
                invitation.status = InvitationStatus.OPENED.value
                await self._uow.assessment_repository.create_audit_entry(
                    AuditLogORM(
                        id=uuid4(), actor_type="candidate", actor_id=None,
                        action="invitation.opened", organization_id=invitation.organization_id,
                        vacancy_id=invitation.vacancy_id, invitation_id=invitation.id,
                    )
                )
        if unavailable:
            raise AssessmentFlowError()
        return invitation

    async def start(self, token: str, email: str, display_name: str | None, consent_version: str) -> CandidateAttemptORM:
        normalized_email = email.strip().casefold()
        unavailable = False
        async with self._uow:
            invitation = await self._uow.assessment_repository.get_invitation_by_hash_for_update(self._tokens.hash(token))
            if invitation is None or invitation.expires_at <= utcnow() or invitation.status in {
                InvitationStatus.REVOKED.value, InvitationStatus.COMPLETED.value, InvitationStatus.EXPIRED.value,
            } or invitation.candidate_email_normalized != normalized_email:
                if invitation is not None and invitation.expires_at <= utcnow():
                    invitation.status = InvitationStatus.EXPIRED.value
                unavailable = True
            else:
                existing = await self._uow.assessment_repository.get_attempt_for_invitation(invitation.id)
                if existing is not None:
                    return existing
                if invitation.attempts_started >= invitation.max_attempts:
                    unavailable = True
                else:
                    invitation.attempts_started += 1
                    invitation.status = InvitationStatus.IN_PROGRESS.value
                    attempt = CandidateAttemptORM(
                        id=uuid4(), invitation_id=invitation.id, candidate_email_normalized=normalized_email,
                        candidate_display_name=(display_name or "").strip() or None, consent_version=consent_version,
                        consented_at=utcnow(), status=AttemptStatus.CREATED.value, started_at=utcnow(),
                    )
                    attempt = await self._uow.assessment_repository.create_attempt(attempt)
                    await self._uow.assessment_repository.create_audit_entry(
                        AuditLogORM(
                            id=uuid4(), actor_type="candidate", actor_id=None,
                            action="invitation.started", organization_id=invitation.organization_id,
                            vacancy_id=invitation.vacancy_id, invitation_id=invitation.id,
                            attempt_id=attempt.id, after={"consent_version": consent_version},
                        )
                    )
        if unavailable:
            raise AssessmentFlowError()
        return attempt


class RevokeInvitationUseCase:
    def __init__(self, uow: IUnitOfWork): self._uow = uow

    async def __call__(self, organization_id: UUID, invitation_id: UUID, actor_user_id: UUID) -> CandidateInvitationORM:
        async with self._uow:
            invitation = await self._uow.assessment_repository.get_invitation(organization_id, invitation_id)
            if invitation is None:
                raise NotFoundError("Invitation not found")
            if invitation.status not in {InvitationStatus.COMPLETED.value, InvitationStatus.EXPIRED.value}:
                invitation.status, invitation.revoked_at, invitation.revoked_by = InvitationStatus.REVOKED.value, utcnow(), actor_user_id
                await self._uow.assessment_repository.create_audit_entry(
                    AuditLogORM(
                        id=uuid4(), actor_type="user", actor_id=actor_user_id,
                        action="invitation.revoked", organization_id=organization_id,
                        vacancy_id=invitation.vacancy_id, invitation_id=invitation.id,
                    )
                )
            return invitation


class UploadAttemptCVUseCase:
    """Persist and enqueue an anonymous candidate CV under its attempt boundary."""

    def __init__(self, uow: IUnitOfWork, s3_client, producer):
        self._uow, self._s3, self._producer = uow, s3_client, producer

    async def __call__(self, attempt_id: UUID, file_bytes: bytes, filename: str, content_type: str) -> AssessmentCVUploadORM:
        # Reuse the same strict validation as the authenticated CV endpoint.
        from src.application.use_cases.cv.upload_cv_use_case import UploadCVUseCase

        # Keeping one canonical validator prevents the public path from
        # drifting from authenticated CV validation.
        UploadCVUseCase.validate_upload(file_bytes, content_type)
        async with self._uow:
            attempt = await self._uow.assessment_repository.get_attempt(attempt_id)
            if attempt is None:
                raise AssessmentFlowError()
            existing = await self._uow.assessment_repository.get_cv_upload_for_attempt(attempt_id)
            if existing is not None:
                return existing
            correlation_id = uuid4()
            key = f"assessment-cvs/{attempt_id}/{correlation_id}.pdf"
            try:
                await self._s3.put_object(key=key, body=file_bytes, content_type=content_type)
            except Exception as exc:
                raise AssessmentFlowError() from exc
            upload = await self._uow.assessment_repository.create_cv_upload(AssessmentCVUploadORM(
                id=uuid4(), attempt_id=attempt_id, correlation_id=correlation_id, s3_object_key=key,
                original_filename=filename or None, status=AnalysisStatus.PENDING.value,
            ))
            attempt.cv_correlation_id = correlation_id
            attempt.status = AttemptStatus.CV_PROCESSING.value
        try:
            await self._producer.send_message(CVAnalysisJobMessage(
                correlation_id=upload.correlation_id, user_id=attempt_id, s3_object_key=upload.s3_object_key,
                original_filename=upload.original_filename, published_at=datetime.now(UTC),
            ).model_dump_json())
        except Exception as exc:
            async with self._uow:
                upload.status, upload.error_code = AnalysisStatus.FAILED.value, "PUBLISH_FAILED"
                attempt = await self._uow.assessment_repository.get_attempt(attempt_id)
                if attempt:
                    attempt.status, attempt.failure_code = AttemptStatus.FAILED.value, "PUBLISH_FAILED"
            raise AssessmentFlowError() from exc
        return upload


class CompleteAttemptUseCase:
    def __init__(self, uow: IUnitOfWork): self._uow = uow

    async def __call__(self, attempt_id: UUID, session_id: str, report_reference: str) -> CandidateAttemptORM:
        async with self._uow:
            attempt = await self._uow.assessment_repository.get_attempt(attempt_id)
            if attempt is None or attempt.status not in {AttemptStatus.READY.value, AttemptStatus.IN_PROGRESS.value, AttemptStatus.COMPLETED.value}:
                raise AssessmentFlowError()
            if attempt.status != AttemptStatus.COMPLETED.value:
                attempt.status, attempt.completed_at = AttemptStatus.COMPLETED.value, utcnow()
                attempt.interview_session_id, attempt.report_reference, attempt.report_version = session_id, report_reference, 1
            return attempt
