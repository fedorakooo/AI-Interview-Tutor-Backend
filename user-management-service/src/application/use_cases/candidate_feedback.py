from uuid import UUID, uuid4, uuid5

from shared_models.assessment.contracts import AttemptStatus

from src.application.mappers.candidate_feedback_email import CANDIDATE_FEEDBACK_EVENT_TYPE
from src.domain.exceptions.not_found_error import NotFoundError
from src.domain.interfaces.database.uow import IUnitOfWork
from src.domain.interfaces.reports.interview_feedback_client import IInterviewFeedbackClient
from src.infrastructure.postgres.schemas.assessment_flow import AssessmentOutboxORM, AuditLogORM

FEEDBACK_NAMESPACE = UUID("9c1d2e3f-4a5b-4c6d-8e7f-a1b2c3d4e5f6")
FEEDBACK_SUBJECT = "Feedback on your interview"


class FeedbackNotAvailableError(Exception):
    pass


class FeedbackVersionMismatchError(Exception):
    pass


class ApproveCandidateFeedbackUseCase:
    def __init__(self, uow: IUnitOfWork, feedback_client: IInterviewFeedbackClient):
        self._uow = uow
        self._feedback_client = feedback_client

    async def __call__(self, organization_id: UUID, attempt_id: UUID, actor_user_id: UUID, version: int) -> bool:
        """Queue the approved feedback email once and report whether this call queued it."""
        async with self._uow:
            attempt = await self._uow.assessment_repository.get_attempt_for_organization(organization_id, attempt_id)
            if attempt is None:
                raise NotFoundError("Assessment attempt not found")
            if attempt.status != AttemptStatus.COMPLETED.value:
                raise FeedbackNotAvailableError()
            row = await self._uow.assessment_repository.get_attempt_with_invitation(attempt_id)
            if row is None:
                raise NotFoundError("Assessment attempt not found")
            _, invitation = row

        feedback = await self._feedback_client.get_feedback(attempt_id)
        if feedback.version != version:
            raise FeedbackVersionMismatchError()

        event_id = uuid5(FEEDBACK_NAMESPACE, f"candidate-feedback/{attempt_id}")
        async with self._uow:
            if await self._uow.assessment_repository.has_outbox_message(CANDIDATE_FEEDBACK_EVENT_TYPE, event_id):
                return False
            await self._uow.assessment_repository.create_outbox_message(
                AssessmentOutboxORM(
                    id=uuid4(),
                    event_id=event_id,
                    event_type=CANDIDATE_FEEDBACK_EVENT_TYPE,
                    # The candidate address is resolved at dispatch time and is never copied here.
                    payload={
                        "attempt_id": str(attempt_id),
                        "subject": FEEDBACK_SUBJECT,
                        "body": feedback.text,
                        "version": feedback.version,
                    },
                )
            )
            await self._uow.assessment_repository.create_audit_entry(
                AuditLogORM(
                    id=uuid4(),
                    actor_type="user",
                    actor_id=actor_user_id,
                    action="candidate_feedback.approved",
                    organization_id=organization_id,
                    vacancy_id=invitation.vacancy_id,
                    invitation_id=invitation.id,
                    attempt_id=attempt_id,
                    after={"version": feedback.version, "source": feedback.source},
                )
            )
            return True
