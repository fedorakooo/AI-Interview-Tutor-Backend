from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from shared_models.assessment.contracts import AttemptStatus, InvitationStatus, VacancyStatus

from src.config import settings
from src.domain.exceptions.not_found_error import NotFoundError
from src.domain.interfaces.database.uow import IUnitOfWork
from src.infrastructure.postgres.schemas.assessment_flow import CandidateAttemptORM, CandidateInvitationORM


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
            return await self._uow.assessment_repository.create_invitation(invitation), token


class PublicInvitationUseCase:
    def __init__(self, uow: IUnitOfWork, token_handler):
        self._uow, self._tokens = uow, token_handler

    async def preflight(self, token: str) -> CandidateInvitationORM:
        async with self._uow:
            invitation = await self._uow.assessment_repository.get_invitation_by_hash_for_update(self._tokens.hash(token))
            if invitation is None or invitation.status in {InvitationStatus.REVOKED.value, InvitationStatus.COMPLETED.value}:
                raise AssessmentFlowError()
            if invitation.expires_at <= utcnow():
                invitation.status = InvitationStatus.EXPIRED.value
                raise AssessmentFlowError()
            if invitation.status == InvitationStatus.CREATED.value:
                invitation.status = InvitationStatus.OPENED.value
            return invitation

    async def start(self, token: str, email: str, display_name: str | None, consent_version: str) -> CandidateAttemptORM:
        normalized_email = email.strip().casefold()
        async with self._uow:
            invitation = await self._uow.assessment_repository.get_invitation_by_hash_for_update(self._tokens.hash(token))
            if invitation is None or invitation.expires_at <= utcnow() or invitation.status in {
                InvitationStatus.REVOKED.value, InvitationStatus.COMPLETED.value, InvitationStatus.EXPIRED.value,
            } or invitation.candidate_email_normalized != normalized_email:
                if invitation is not None and invitation.expires_at <= utcnow():
                    invitation.status = InvitationStatus.EXPIRED.value
                raise AssessmentFlowError()
            existing = await self._uow.assessment_repository.get_attempt_for_invitation(invitation.id)
            if existing is not None:
                return existing
            if invitation.attempts_started >= invitation.max_attempts:
                raise AssessmentFlowError()
            invitation.attempts_started += 1
            invitation.status = InvitationStatus.IN_PROGRESS.value
            attempt = CandidateAttemptORM(
                id=uuid4(), invitation_id=invitation.id, candidate_email_normalized=normalized_email,
                candidate_display_name=(display_name or "").strip() or None, consent_version=consent_version,
                consented_at=utcnow(), status=AttemptStatus.CREATED.value, started_at=utcnow(),
            )
            return await self._uow.assessment_repository.create_attempt(attempt)


class RevokeInvitationUseCase:
    def __init__(self, uow: IUnitOfWork): self._uow = uow

    async def __call__(self, organization_id: UUID, invitation_id: UUID, actor_user_id: UUID) -> CandidateInvitationORM:
        async with self._uow:
            invitation = await self._uow.assessment_repository.get_invitation(organization_id, invitation_id)
            if invitation is None:
                raise NotFoundError("Invitation not found")
            if invitation.status not in {InvitationStatus.COMPLETED.value, InvitationStatus.EXPIRED.value}:
                invitation.status, invitation.revoked_at, invitation.revoked_by = InvitationStatus.REVOKED.value, utcnow(), actor_user_id
            return invitation
