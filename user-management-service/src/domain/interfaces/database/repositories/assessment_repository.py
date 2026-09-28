from abc import ABC, abstractmethod
from uuid import UUID

from src.infrastructure.postgres.schemas.assessment_flow import AssessmentCVUploadORM, AuditLogORM, CandidateAttemptORM, CandidateInvitationORM, HumanDecisionORM


class IAssessmentRepository(ABC):
    @abstractmethod
    async def create_invitation(self, invitation: CandidateInvitationORM) -> CandidateInvitationORM: ...

    @abstractmethod
    async def list_invitations(self, organization_id: UUID, vacancy_id: UUID) -> list[CandidateInvitationORM]: ...

    @abstractmethod
    async def get_invitation(self, organization_id: UUID, invitation_id: UUID) -> CandidateInvitationORM | None: ...

    @abstractmethod
    async def get_invitation_by_hash_for_update(self, token_hash: str) -> CandidateInvitationORM | None: ...

    @abstractmethod
    async def create_attempt(self, attempt: CandidateAttemptORM) -> CandidateAttemptORM: ...

    @abstractmethod
    async def get_attempt_for_invitation(self, invitation_id: UUID) -> CandidateAttemptORM | None: ...

    @abstractmethod
    async def get_attempt(self, attempt_id: UUID) -> CandidateAttemptORM | None: ...

    @abstractmethod
    async def create_cv_upload(self, upload: AssessmentCVUploadORM) -> AssessmentCVUploadORM: ...

    @abstractmethod
    async def get_cv_upload_for_attempt(self, attempt_id: UUID) -> AssessmentCVUploadORM | None: ...

    @abstractmethod
    async def get_cv_upload_by_correlation_id(self, correlation_id: UUID) -> AssessmentCVUploadORM | None: ...

    @abstractmethod
    async def get_attempt_for_organization(self, organization_id: UUID, attempt_id: UUID) -> CandidateAttemptORM | None: ...

    @abstractmethod
    async def list_attempts_for_vacancy(self, organization_id: UUID, vacancy_id: UUID, limit: int, offset: int) -> list[CandidateAttemptORM]: ...

    @abstractmethod
    async def get_decision(self, attempt_id: UUID) -> HumanDecisionORM | None: ...

    @abstractmethod
    async def upsert_decision(self, attempt_id: UUID, decision: str, private_note: str | None, actor_user_id: UUID) -> HumanDecisionORM: ...

    @abstractmethod
    async def create_audit_entry(self, entry: AuditLogORM) -> AuditLogORM: ...
