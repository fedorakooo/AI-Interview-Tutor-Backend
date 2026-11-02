from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest
from shared_models.assessment import FeedbackEditRequest, FeedbackView
from shared_models.assessment.contracts import AttemptStatus
from shared_models.messaging.notifications import NotificationEmailMessage
from src.application.mappers.candidate_feedback_email import (
    CANDIDATE_FEEDBACK_EVENT_TYPE,
    build_candidate_feedback_email,
)
from src.application.use_cases.candidate_feedback import (
    ApproveCandidateFeedbackUseCase,
    FeedbackNotAvailableError,
    FeedbackVersionMismatchError,
)
from src.domain.exceptions.interview_report_errors import (
    InterviewReportNotFoundError,
    InterviewReportUnavailableError,
)
from src.domain.exceptions.not_found_error import NotFoundError
from src.domain.interfaces.reports.interview_feedback_client import IInterviewFeedbackClient
from src.infrastructure.interview_service.feedback_client import InterviewServiceFeedbackClient

NOW = datetime(2026, 11, 3, tzinfo=UTC)


def feedback(attempt_id: UUID, version: int = 2, text: str = "Thank you, great work!") -> FeedbackView:
    return FeedbackView(
        attempt_id=attempt_id, version=version, text=text, source="edited", editor_id=uuid4(), created_at=NOW
    )


class FakeFeedbackClient(IInterviewFeedbackClient):
    def __init__(self, view: FeedbackView, error: Exception | None = None) -> None:
        self.view = view
        self.error = error

    async def get_feedback(self, attempt_id: UUID) -> FeedbackView:
        if self.error:
            raise self.error
        return self.view

    async def edit_feedback(self, attempt_id: UUID, request: FeedbackEditRequest) -> FeedbackView:
        return self.view


class FakeAssessmentRepository:
    def __init__(self, attempt, invitation) -> None:
        self.attempt, self.invitation = attempt, invitation
        self.outbox = []
        self.audit_entries = []

    async def get_attempt_for_organization(self, organization_id, attempt_id):
        ok = attempt_id == self.attempt.id and organization_id == self.invitation.organization_id
        return self.attempt if ok else None

    async def get_attempt_with_invitation(self, attempt_id):
        return (self.attempt, self.invitation) if attempt_id == self.attempt.id else None

    async def has_outbox_message(self, event_type, event_id):
        return any(m.event_type == event_type and m.event_id == event_id for m in self.outbox)

    async def create_outbox_message(self, message):
        self.outbox.append(message)
        return message

    async def create_audit_entry(self, entry):
        self.audit_entries.append(entry)
        return entry


class FakeUow:
    def __init__(self, repository) -> None:
        self.assessment_repository = repository

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None


def state(status: str = AttemptStatus.COMPLETED.value):
    invitation = SimpleNamespace(id=uuid4(), organization_id=uuid4(), vacancy_id=uuid4())
    attempt = SimpleNamespace(id=uuid4(), status=status, candidate_email_normalized="ada@example.com")
    return attempt, invitation, FakeAssessmentRepository(attempt, invitation)


@pytest.mark.asyncio
async def test_approval_queues_the_text_once_without_the_candidate_address_and_is_audited():
    attempt, invitation, repository = state()
    actor = uuid4()
    use_case = ApproveCandidateFeedbackUseCase(FakeUow(repository), FakeFeedbackClient(feedback(attempt.id)))

    first = await use_case(invitation.organization_id, attempt.id, actor, 2)
    second = await use_case(invitation.organization_id, attempt.id, actor, 2)

    assert (first, second) == (True, False)
    [message] = repository.outbox
    assert message.event_type == CANDIDATE_FEEDBACK_EVENT_TYPE
    assert message.payload["body"] == "Thank you, great work!" and message.payload["attempt_id"] == str(attempt.id)
    assert "ada@example.com" not in str(message.payload)
    [entry] = repository.audit_entries
    assert (entry.action, entry.actor_id, entry.after) == (
        "candidate_feedback.approved",
        actor,
        {"version": 2, "source": "edited"},
    )
    assert "Thank you" not in str(entry.after) and "ada@example.com" not in str(entry.after)


@pytest.mark.asyncio
async def test_stale_version_is_refused_and_nothing_is_queued():
    attempt, invitation, repository = state()
    use_case = ApproveCandidateFeedbackUseCase(FakeUow(repository), FakeFeedbackClient(feedback(attempt.id, version=3)))

    with pytest.raises(FeedbackVersionMismatchError):
        await use_case(invitation.organization_id, attempt.id, uuid4(), 2)
    assert repository.outbox == [] and repository.audit_entries == []


@pytest.mark.asyncio
async def test_unfinished_foreign_and_missing_feedback_are_rejected():
    attempt, invitation, repository = state(AttemptStatus.IN_PROGRESS.value)
    client = FakeFeedbackClient(feedback(attempt.id))

    with pytest.raises(FeedbackNotAvailableError):
        await ApproveCandidateFeedbackUseCase(FakeUow(repository), client)(
            invitation.organization_id, attempt.id, uuid4(), 2
        )

    attempt, invitation, repository = state()
    with pytest.raises(NotFoundError):
        await ApproveCandidateFeedbackUseCase(FakeUow(repository), client)(uuid4(), attempt.id, uuid4(), 2)
    with pytest.raises(InterviewReportNotFoundError):
        await ApproveCandidateFeedbackUseCase(
            FakeUow(repository), FakeFeedbackClient(feedback(attempt.id), InterviewReportNotFoundError())
        )(invitation.organization_id, attempt.id, uuid4(), 2)
    assert repository.outbox == []


def test_email_message_joins_the_address_at_dispatch_time():
    attempt_id = uuid4()
    payload = {
        "attempt_id": str(attempt_id),
        "subject": "Feedback on your interview",
        "body": "Well done",
        "version": 1,
    }

    message = NotificationEmailMessage.model_validate_json(
        build_candidate_feedback_email(payload, "ada@example.com", NOW)
    )

    assert (message.email, message.email_type, message.user_id, message.body) == (
        "ada@example.com",
        "candidate_feedback",
        str(attempt_id),
        "Well done",
    )
    assert message.published_at == NOW.isoformat()


@pytest.mark.asyncio
async def test_feedback_client_fetches_and_edits_with_the_internal_token():
    attempt_id = uuid4()
    view = feedback(attempt_id)
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path, request.headers["X-Internal-Service-Token"], request.content))
        return httpx.Response(200, content=view.model_dump_json())

    client = InterviewServiceFeedbackClient(
        "http://interview-service:8001", "secret", transport=httpx.MockTransport(handler)
    )
    editor = uuid4()

    assert await client.get_feedback(attempt_id) == view
    assert await client.edit_feedback(attempt_id, FeedbackEditRequest(editor_id=editor, text="New text")) == view

    assert seen[0][:3] == ("GET", f"/api/internal/feedback/{attempt_id}", "secret")
    assert seen[1][:3] == ("PUT", f"/api/internal/feedback/{attempt_id}", "secret")
    assert b"New text" in seen[1][3] and str(editor).encode() in seen[1][3]


@pytest.mark.asyncio
async def test_feedback_client_maps_failures():
    client = InterviewServiceFeedbackClient(
        "http://interview-service:8001", "secret", transport=httpx.MockTransport(lambda request: httpx.Response(404))
    )
    with pytest.raises(InterviewReportNotFoundError):
        await client.get_feedback(uuid4())

    broken = InterviewServiceFeedbackClient(
        "http://interview-service:8001", "secret", transport=httpx.MockTransport(lambda request: httpx.Response(500))
    )
    with pytest.raises(InterviewReportUnavailableError):
        await broken.get_feedback(uuid4())
