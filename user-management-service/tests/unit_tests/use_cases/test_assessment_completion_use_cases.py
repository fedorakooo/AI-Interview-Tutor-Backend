from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from shared_models.assessment.contracts import (
    AssessmentCompleted,
    AssessmentMode,
    AssessmentTemplateSnapshot,
    AttemptStatus,
    RubricCriterion,
)

from src.application.use_cases.assessments import (
    AssessmentFlowError,
    GetAssessmentContextUseCase,
    RegisterAssessmentCompletionUseCase,
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
    )
    attempt = SimpleNamespace(
        id=attempt_id,
        status=AttemptStatus.READY.value,
        cv_correlation_id=uuid4(),
        candidate_display_name="Ada Candidate",
        completed_at=None,
        interview_session_id=None,
        report_reference=None,
        report_version=None,
    )
    return attempt, invitation


def _event(attempt, invitation):
    return AssessmentCompleted(
        event_id=uuid4(), occurred_at=datetime.now(UTC), correlation_id=uuid4(),
        organization_id=invitation.organization_id, vacancy_id=invitation.vacancy_id,
        invitation_id=invitation.id, attempt_id=attempt.id, session_id="session-1",
        report_reference="opaque-report-reference", report_version=2,
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
        mode=AssessmentMode.TECHNICAL, question_count=5, duration_minutes=30, attempt_limit=1,
        criteria=[RubricCriterion(skill="Python", required=True, weight=100, expected_level="senior")],
    )
    vacancy = SimpleNamespace(id=invitation.vacancy_id, organization_id=invitation.organization_id, status="active")
    template = SimpleNamespace(version=1, snapshot=snapshot)

    context = await GetAssessmentContextUseCase(_Uow(repository, _VacancyRepository(vacancy, template)))(attempt.id)

    assert context.attempt_id == attempt.id
    assert context.template == snapshot
    assert context.cv_correlation_id == attempt.cv_correlation_id
    assert "candidate_email_normalized" not in type(context).model_fields
