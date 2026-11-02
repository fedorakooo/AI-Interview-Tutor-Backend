from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from shared_models.assessment.contracts import (
    AssessmentCompleted,
    AssessmentMode,
    AssessmentTemplateSnapshot,
    AttemptStatus,
    CvPolicy,
    RubricCriterion,
)
from src.domain.exceptions.not_found_error import NotFoundError
from src.application.use_cases.assessments import (
    AssessmentFlowError,
    EnsureInterviewAccessUseCase,
    GetAssessmentContextUseCase,
    RegisterAssessmentCompletionUseCase,
    SkipAttemptCVUseCase,
)


class _AssessmentRepository:
    def __init__(self, attempt, invitation):
        self.attempt = attempt
        self.invitation = invitation
        self.claimed_events = set()
        self.audit_entries = []
        self.outbox_messages = []

    async def claim_event(self, consumer_name, event_id):
        key = (consumer_name, event_id)
        if key in self.claimed_events:
            return False
        self.claimed_events.add(key)
        return True

    async def get_attempt_with_invitation(self, attempt_id):
        if attempt_id != self.attempt.id:
            return None
        return self.attempt, self.invitation

    async def create_audit_entry(self, entry):
        self.audit_entries.append(entry)
        return entry

    async def create_outbox_message(self, message):
        self.outbox_messages.append(message)
        return message


class _VacancyRepository:
    def __init__(self, vacancy, template):
        self.vacancy = vacancy
        self.template = template

    async def get_by_id_and_organization_id(self, vacancy_id, organization_id):
        if vacancy_id == self.vacancy.id and organization_id == self.vacancy.organization_id:
            return self.vacancy
        return None

    async def get_template(self, vacancy_id, version):
        return self.template if vacancy_id == self.vacancy.id and version == self.template.version else None


class _Uow:
    def __init__(self, assessment_repository, vacancy_repository=None):
        self.assessment_repository = assessment_repository
        self.vacancy_repository = vacancy_repository

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None


def _state():
    organization_id, vacancy_id, invitation_id, attempt_id = uuid4(), uuid4(), uuid4(), uuid4()
    invitation = SimpleNamespace(
        id=invitation_id,
        organization_id=organization_id,
        vacancy_id=vacancy_id,
        template_version=1,
        status="in_progress",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    attempt = SimpleNamespace(
        id=attempt_id,
        status=AttemptStatus.READY.value,
        cv_correlation_id=uuid4(),
        candidate_display_name="Ada Candidate",
        candidate_email_normalized="ada@example.com",
        completed_at=None,
        interview_session_id=None,
        report_reference=None,
        report_version=None,
    )
    return attempt, invitation


def _event(attempt, invitation):
    return AssessmentCompleted(
        event_id=uuid4(),
        occurred_at=datetime.now(UTC),
        correlation_id=uuid4(),
        organization_id=invitation.organization_id,
        vacancy_id=invitation.vacancy_id,
        invitation_id=invitation.id,
        attempt_id=attempt.id,
        session_id="session-1",
        report_reference="opaque-report-reference",
        report_version=2,
    )


@pytest.mark.asyncio
async def test_completion_event_is_idempotent_and_only_audited_once():
    attempt, invitation = _state()
    repository = _AssessmentRepository(attempt, invitation)
    use_case = RegisterAssessmentCompletionUseCase(_Uow(repository))
    event = _event(attempt, invitation)

    completed = await use_case(event)
    duplicate = await use_case(event)

    assert completed is attempt
    assert duplicate is None
    assert attempt.status == AttemptStatus.COMPLETED.value
    assert attempt.report_reference == "opaque-report-reference"
    assert invitation.status == "completed"
    assert [entry.action for entry in repository.audit_entries] == ["assessment.completed"]
    assert "report_reference" not in repository.audit_entries[0].after
    assert len(repository.outbox_messages) == 1
    assert repository.outbox_messages[0].payload["notification_type"] == "assessment_completed"
    assert "report_reference" not in repository.outbox_messages[0].payload


@pytest.mark.asyncio
async def test_completion_rejects_event_for_another_tenant_before_writing_report():
    attempt, invitation = _state()
    repository = _AssessmentRepository(attempt, invitation)
    event = _event(attempt, invitation).model_copy(update={"organization_id": uuid4()})

    with pytest.raises(AssessmentFlowError):
        await RegisterAssessmentCompletionUseCase(_Uow(repository))(event)

    assert attempt.report_reference is None
    assert repository.audit_entries == []


@pytest.mark.asyncio
async def test_context_comes_from_persisted_attempt_template_and_not_browser_values():
    attempt, invitation = _state()
    repository = _AssessmentRepository(attempt, invitation)
    snapshot = AssessmentTemplateSnapshot(
        mode=AssessmentMode.TECHNICAL,
        question_count=5,
        duration_minutes=30,
        attempt_limit=1,
        criteria=[RubricCriterion(skill="Python", required=True, weight=100, expected_level="senior")],
    )
    vacancy = SimpleNamespace(
        id=invitation.vacancy_id,
        organization_id=invitation.organization_id,
        status="active",
        job_description="Build APIs",
    )
    template = SimpleNamespace(version=1, snapshot=snapshot)

    context = await GetAssessmentContextUseCase(_Uow(repository, _VacancyRepository(vacancy, template)))(attempt.id)

    assert context.attempt_id == attempt.id
    assert context.template == snapshot
    assert context.cv_correlation_id == attempt.cv_correlation_id
    assert "candidate_email_normalized" not in type(context).model_fields


def _context_use_case(policy, *, attempt_status=AttemptStatus.READY.value, cv_correlation_id=None, brief=""):
    attempt, invitation = _state()
    attempt.status, attempt.cv_correlation_id = attempt_status, cv_correlation_id
    snapshot = AssessmentTemplateSnapshot(
        mode=AssessmentMode.TECHNICAL,
        question_count=5,
        duration_minutes=30,
        attempt_limit=1,
        cv_policy=policy,
        brief=brief,
        criteria=[RubricCriterion(skill="Python", required=True, weight=100, expected_level="senior")],
    )
    vacancy = SimpleNamespace(
        id=invitation.vacancy_id,
        organization_id=invitation.organization_id,
        status="active",
        job_description="Build APIs",
    )
    uow = _Uow(
        _AssessmentRepository(attempt, invitation),
        _VacancyRepository(vacancy, SimpleNamespace(version=1, snapshot=snapshot)),
    )
    return attempt, GetAssessmentContextUseCase(uow), vacancy


@pytest.mark.asyncio
@pytest.mark.parametrize("policy", [CvPolicy.OPTIONAL, CvPolicy.NONE])
async def test_context_does_not_require_a_cv_when_the_policy_allows_none(policy):
    attempt, use_case, _ = _context_use_case(policy, brief="Focus on APIs")

    context = await use_case(attempt.id)

    assert context.cv_correlation_id is None
    assert context.cv_policy == policy
    assert context.job_description == "Build APIs"
    assert context.brief == "Focus on APIs"


@pytest.mark.asyncio
async def test_context_requires_a_cv_when_the_policy_requires_one():
    attempt, use_case, _ = _context_use_case(CvPolicy.REQUIRED)

    with pytest.raises(AssessmentFlowError):
        await use_case(attempt.id)


@pytest.mark.asyncio
async def test_completed_attempt_context_is_available_for_reports_even_after_the_vacancy_closes():
    attempt, use_case, vacancy = _context_use_case(CvPolicy.NONE, attempt_status=AttemptStatus.COMPLETED.value)
    vacancy.status = "closed"

    assert (await use_case(attempt.id)).attempt_id == attempt.id


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [AttemptStatus.CREATED.value, AttemptStatus.CV_PROCESSING.value])
async def test_context_is_unavailable_before_the_attempt_is_ready(status):
    attempt, use_case, _ = _context_use_case(CvPolicy.NONE, attempt_status=status)

    with pytest.raises(AssessmentFlowError):
        await use_case(attempt.id)


def _skip_use_case(policy, status=AttemptStatus.CREATED.value):
    attempt, invitation = _state()
    attempt.status, attempt.cv_correlation_id = status, None

    class Repository(_AssessmentRepository):
        async def get_attempt(self, attempt_id):
            return self.attempt if attempt_id == self.attempt.id else None

    snapshot = SimpleNamespace(cv_policy=policy)
    vacancy_repository = _VacancyRepository(
        SimpleNamespace(id=invitation.vacancy_id, organization_id=invitation.organization_id),
        SimpleNamespace(version=1, snapshot=snapshot),
    )
    return attempt, SkipAttemptCVUseCase(_Uow(Repository(attempt, invitation), vacancy_repository))


@pytest.mark.asyncio
async def test_optional_cv_can_be_skipped_once_to_make_the_attempt_ready():
    attempt, use_case = _skip_use_case(CvPolicy.OPTIONAL)

    assert (await use_case(attempt.id)).status == AttemptStatus.READY.value
    assert (await use_case(attempt.id)).status == AttemptStatus.READY.value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("policy", "status"),
    [
        (CvPolicy.REQUIRED, AttemptStatus.CREATED.value),
        (CvPolicy.NONE, AttemptStatus.CREATED.value),
        (CvPolicy.OPTIONAL, AttemptStatus.CV_PROCESSING.value),
    ],
)
async def test_cv_cannot_be_skipped_when_it_is_required_or_already_uploaded(policy, status):
    attempt, use_case = _skip_use_case(policy, status)

    with pytest.raises(AssessmentFlowError):
        await use_case(attempt.id)
    assert attempt.status == status


@pytest.mark.asyncio
@pytest.mark.parametrize("invitation_status", ["revoked", "expired"])
async def test_context_and_interview_access_are_refused_for_a_revoked_or_expired_invitation(invitation_status):
    attempt, use_case, _ = _context_use_case(CvPolicy.NONE)
    repository = use_case._uow.assessment_repository
    repository.invitation.status = invitation_status

    with pytest.raises(AssessmentFlowError):
        await use_case(attempt.id)
    with pytest.raises(AssessmentFlowError):
        await EnsureInterviewAccessUseCase(use_case._uow)(attempt.id)


@pytest.mark.asyncio
async def test_context_and_interview_access_are_refused_after_the_invitation_deadline():
    attempt, use_case, _ = _context_use_case(CvPolicy.NONE)
    use_case._uow.assessment_repository.invitation.expires_at = datetime.now(UTC) - timedelta(seconds=1)

    with pytest.raises(AssessmentFlowError):
        await use_case(attempt.id)
    with pytest.raises(AssessmentFlowError):
        await EnsureInterviewAccessUseCase(use_case._uow)(attempt.id)


@pytest.mark.asyncio
async def test_interview_access_is_allowed_for_a_ready_attempt_and_refused_otherwise():
    attempt, use_case, _ = _context_use_case(CvPolicy.NONE)
    access = EnsureInterviewAccessUseCase(use_case._uow)

    await access(attempt.id)
    with pytest.raises(NotFoundError):
        await access(uuid4())
    attempt.status = AttemptStatus.CV_PROCESSING.value
    with pytest.raises(AssessmentFlowError):
        await access(attempt.id)


@pytest.mark.asyncio
async def test_completed_attempt_context_stays_available_after_the_invitation_expires():
    attempt, use_case, _ = _context_use_case(CvPolicy.NONE, attempt_status=AttemptStatus.COMPLETED.value)
    use_case._uow.assessment_repository.invitation.expires_at = datetime.now(UTC) - timedelta(days=30)

    assert (await use_case(attempt.id)).attempt_id == attempt.id


@pytest.mark.asyncio
async def test_a_repeated_completion_event_is_ignored_after_the_attempt_was_erased():
    from src.application.use_cases.data_erasure import erased_email

    attempt, invitation = _state()
    repository = _AssessmentRepository(attempt, invitation)
    use_case = RegisterAssessmentCompletionUseCase(_Uow(repository))
    event = _event(attempt, invitation)
    await use_case(event)
    attempt.candidate_email_normalized = erased_email(attempt.id)
    attempt.report_reference = None
    attempt.interview_session_id = None

    redelivered = event.model_copy(update={"event_id": uuid4()})

    assert await use_case(redelivered) is attempt
    assert attempt.report_reference is None
