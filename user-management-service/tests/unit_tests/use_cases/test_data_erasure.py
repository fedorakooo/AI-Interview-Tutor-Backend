import logging
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest
from shared_models.assessment import ErasureResult
from sqlalchemy.dialects import postgresql
from src.application.use_cases.data_erasure import (
    ERASED_OBJECT_KEY,
    EraseAttemptDataUseCase,
    EraseExpiredInvitationUseCase,
    PurgeExpiredAssessmentDataUseCase,
    erased_email,
    is_erased,
)
from src.domain.exceptions.interview_report_errors import InterviewReportUnavailableError
from src.domain.exceptions.not_found_error import NotFoundError
from src.domain.interfaces.reports.interview_data_eraser import IInterviewDataEraser
from src.domain.interfaces.storage.s3_client import IS3Client
from src.infrastructure.interview_service.erasure_client import InterviewServiceErasureClient
from src.infrastructure.postgres.repositories.assessment_repository import AssessmentPostgresRepository


class FakeEraser(IInterviewDataEraser):
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[UUID, UUID | None]] = []

    async def erase(self, attempt_id: UUID, cv_correlation_id: UUID | None) -> ErasureResult:
        self.calls.append((attempt_id, cv_correlation_id))
        if self.error:
            raise self.error
        return ErasureResult(attempt_id=attempt_id, deleted={"events": 4, "cv_documents": 1})


class FakeS3(IS3Client):
    def __init__(self) -> None:
        self.deleted: list[str] = []

    async def put_object(self, key: str, body: bytes, content_type: str) -> None:
        raise AssertionError("not used")

    async def delete_object(self, key: str) -> None:
        self.deleted.append(key)


class FakeRepository:
    def __init__(self, *records) -> None:
        self.records = list(records)
        self.notes_cleared: list[UUID] = []
        self.audit_entries = []

    def _find(self, attempt_id):
        return next((r for r in self.records if r[0].id == attempt_id), None)

    async def get_attempt_for_organization(self, organization_id, attempt_id):
        record = self._find(attempt_id)
        return record[0] if record and record[1].organization_id == organization_id else None

    async def get_attempt_with_invitation(self, attempt_id):
        record = self._find(attempt_id)
        return (record[0], record[1]) if record else None

    async def get_invitation(self, organization_id, invitation_id):
        return next((r[1] for r in self.records if r[1].id == invitation_id), None)

    async def get_cv_upload_for_attempt(self, attempt_id):
        record = self._find(attempt_id)
        return record[2] if record else None

    async def clear_decision_notes(self, attempt_id):
        self.notes_cleared.append(attempt_id)

    async def create_audit_entry(self, entry):
        self.audit_entries.append(entry)
        return entry

    async def list_attempts_due_for_erasure(self, limit):
        return [(a, i) for a, i, _ in self.records if not is_erased(a.candidate_email_normalized)]

    async def list_invitations_due_for_erasure(self, limit):
        return []


class FakeUow:
    def __init__(self, repository) -> None:
        self.assessment_repository = repository

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None


def records(with_upload: bool = True):
    invitation = SimpleNamespace(
        id=uuid4(), organization_id=uuid4(), vacancy_id=uuid4(), candidate_email_normalized="ada@example.com"
    )
    attempt = SimpleNamespace(
        id=uuid4(),
        candidate_email_normalized="ada@example.com",
        candidate_display_name="Ada Candidate",
        report_reference="interview-report:x",
        interview_session_id="x",
        cv_correlation_id=uuid4(),
    )
    upload = (
        SimpleNamespace(s3_object_key="assessment-cvs/a/b.pdf", original_filename="ada-cv.pdf", mongo_document_id="m1")
        if with_upload
        else None
    )
    return attempt, invitation, upload, FakeRepository((attempt, invitation, upload))


@pytest.mark.asyncio
async def test_erasure_removes_remote_data_and_anonymizes_every_personal_field():
    attempt, invitation, upload, repository = records()
    cv_correlation_id, eraser, s3, actor = attempt.cv_correlation_id, FakeEraser(), FakeS3(), uuid4()

    erased = await EraseAttemptDataUseCase(FakeUow(repository), eraser, s3)(
        invitation.organization_id, attempt.id, actor, "request"
    )

    assert erased is True
    assert eraser.calls == [(attempt.id, cv_correlation_id)] and s3.deleted == ["assessment-cvs/a/b.pdf"]
    assert attempt.candidate_email_normalized == erased_email(attempt.id) and is_erased(
        attempt.candidate_email_normalized
    )
    assert invitation.candidate_email_normalized == erased_email(invitation.id)
    assert (attempt.candidate_display_name, attempt.report_reference, attempt.interview_session_id) == (
        None,
        None,
        None,
    )
    assert (upload.s3_object_key, upload.original_filename, upload.mongo_document_id) == (ERASED_OBJECT_KEY, None, None)
    assert repository.notes_cleared == [attempt.id]
    [entry] = repository.audit_entries
    assert (entry.action, entry.actor_id, entry.after) == (
        "assessment.data_erased",
        actor,
        {"reason": "request", "deleted": {"events": 4, "cv_documents": 1}},
    )
    assert "ada" not in str(entry.after).lower()


@pytest.mark.asyncio
async def test_erasure_is_idempotent_and_skips_remote_calls_the_second_time():
    attempt, invitation, _, repository = records(with_upload=False)
    eraser, s3 = FakeEraser(), FakeS3()
    use_case = EraseAttemptDataUseCase(FakeUow(repository), eraser, s3)

    assert await use_case(invitation.organization_id, attempt.id, None, "retention") is True
    assert await use_case(invitation.organization_id, attempt.id, None, "retention") is False

    assert len(eraser.calls) == 1 and s3.deleted == [] and len(repository.audit_entries) == 1
    assert repository.audit_entries[0].actor_type == "service"


@pytest.mark.asyncio
async def test_failed_remote_erasure_keeps_the_local_data_so_the_run_can_be_retried():
    attempt, invitation, upload, repository = records()
    s3 = FakeS3()

    with pytest.raises(InterviewReportUnavailableError):
        await EraseAttemptDataUseCase(FakeUow(repository), FakeEraser(InterviewReportUnavailableError()), s3)(
            invitation.organization_id, attempt.id, None, "retention"
        )

    assert attempt.candidate_email_normalized == "ada@example.com" and s3.deleted == []
    assert upload.s3_object_key == "assessment-cvs/a/b.pdf" and repository.audit_entries == []


@pytest.mark.asyncio
async def test_attempt_of_another_organization_is_not_found_and_not_erased():
    attempt, _, _, repository = records()
    eraser = FakeEraser()

    with pytest.raises(NotFoundError):
        await EraseAttemptDataUseCase(FakeUow(repository), eraser, FakeS3())(uuid4(), attempt.id, uuid4(), "request")
    assert eraser.calls == [] and attempt.candidate_email_normalized == "ada@example.com"


@pytest.mark.asyncio
async def test_expired_invitation_email_is_anonymized_once():
    attempt, invitation, _, repository = records()
    use_case = EraseExpiredInvitationUseCase(FakeUow(repository))

    assert await use_case(invitation.organization_id, invitation.id) is True
    assert await use_case(invitation.organization_id, invitation.id) is False

    assert invitation.candidate_email_normalized == erased_email(invitation.id)
    assert [entry.action for entry in repository.audit_entries] == ["invitation.data_erased"]


@pytest.mark.asyncio
async def test_purge_erases_due_records_and_continues_after_a_failure():
    failing, healthy = records(), records()
    repository = FakeRepository((failing[0], failing[1], failing[2]), (healthy[0], healthy[1], healthy[2]))

    @asynccontextmanager
    async def factory():
        yield FakeUow(repository)

    class FailingFirst(FakeEraser):
        async def erase(self, attempt_id, cv_correlation_id):
            if attempt_id == failing[0].id:
                raise InterviewReportUnavailableError()
            return await super().erase(attempt_id, cv_correlation_id)

    purge = PurgeExpiredAssessmentDataUseCase(factory, FailingFirst(), FakeS3(), logging.getLogger("test"))

    assert await purge(10) == 1
    assert failing[0].candidate_email_normalized == "ada@example.com"
    assert is_erased(healthy[0].candidate_email_normalized)
    assert await purge(10) == 0


@pytest.mark.asyncio
async def test_erasure_client_posts_the_cv_reference_with_the_internal_token():
    attempt_id, correlation_id = uuid4(), uuid4()
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path, request.headers["X-Internal-Service-Token"], request.content))
        return httpx.Response(200, json={"attempt_id": str(attempt_id), "deleted": {"events": 2}})

    client = InterviewServiceErasureClient(
        "http://interview-service:8001", "secret", transport=httpx.MockTransport(handler)
    )

    result = await client.erase(attempt_id, correlation_id)

    assert result.deleted == {"events": 2}
    method, path, token, content = seen[0]
    assert (method, path, token) == ("POST", f"/api/internal/erasure/{attempt_id}", "secret")
    assert str(correlation_id).encode() in content


def test_due_queries_use_the_organization_retention_days_and_skip_erased_records():
    repository = AssessmentPostgresRepository(session=None)
    captured = []

    class CapturingSession:
        async def execute(self, statement):
            captured.append(str(statement.compile(dialect=postgresql.dialect())))
            return SimpleNamespace(all=lambda: [], scalars=lambda: [])

    repository._session = CapturingSession()
    import asyncio

    asyncio.run(repository.list_attempts_due_for_erasure(5))
    asyncio.run(repository.list_invitations_due_for_erasure(5))

    attempts_sql, invitations_sql = captured
    for sql in captured:
        assert "make_interval" in sql and "organizations.retention_days" in sql and "NOT LIKE" in sql
    assert "coalesce(candidate_attempts.completed_at" in attempts_sql
    assert "candidate_attempts.id IS NULL" in invitations_sql and "candidate_invitations.expires_at" in invitations_sql
