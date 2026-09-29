from types import SimpleNamespace
from uuid import uuid4

import pytest

from shared_models.assessment.contracts import HumanDecisionType

from src.application.use_cases.employer_assessment import GetAuthorizedReportUseCase, RecordHumanDecisionUseCase
from src.domain.exceptions.not_found_error import NotFoundError


class FakeAssessmentRepository:
    def __init__(self, attempts):
        self.attempts = attempts
        self.decisions = {}
        self.audit_entries = []

    async def get_attempt_for_organization(self, organization_id, attempt_id):
        attempt = self.attempts.get(attempt_id)
        return attempt if attempt is not None and attempt.organization_id == organization_id else None

    async def get_decision(self, attempt_id):
        return self.decisions.get(attempt_id)

    async def upsert_decision(self, attempt_id, decision, private_note, actor_user_id):
        existing = self.decisions.get(attempt_id)
        if existing is None:
            existing = SimpleNamespace(decision=decision, private_note=private_note, actor_user_id=actor_user_id, version=1)
            self.decisions[attempt_id] = existing
        else:
            existing.decision = decision
            existing.private_note = private_note
            existing.actor_user_id = actor_user_id
            existing.version += 1
        return existing

    async def create_audit_entry(self, entry):
        self.audit_entries.append(entry)
        return entry


class FakeUow:
    def __init__(self, repository):
        self.assessment_repository = repository

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None


@pytest.mark.asyncio
async def test_report_view_is_organization_scoped_and_audited():
    organization_id, foreign_organization_id, attempt_id, actor_id = uuid4(), uuid4(), uuid4(), uuid4()
    repository = FakeAssessmentRepository({
        attempt_id: SimpleNamespace(id=attempt_id, organization_id=organization_id, report_reference="report-opaque-id"),
    })
    use_case = GetAuthorizedReportUseCase(FakeUow(repository))

    attempt = await use_case(organization_id, attempt_id, actor_id)

    assert attempt.report_reference == "report-opaque-id"
    assert repository.audit_entries[0].action == "assessment_report.viewed"
    assert repository.audit_entries[0].actor_id == actor_id
    with pytest.raises(NotFoundError):
        await use_case(foreign_organization_id, attempt_id, actor_id)


@pytest.mark.asyncio
async def test_decision_update_preserves_previous_value_in_audit_history():
    organization_id, attempt_id, actor_id = uuid4(), uuid4(), uuid4()
    repository = FakeAssessmentRepository({attempt_id: SimpleNamespace(id=attempt_id, organization_id=organization_id)})
    use_case = RecordHumanDecisionUseCase(FakeUow(repository))

    created = await use_case(organization_id, attempt_id, HumanDecisionType.HOLD, "Awaiting references", actor_id)
    assert created.version == 1
    updated = await use_case(organization_id, attempt_id, HumanDecisionType.ADVANCE, "References verified", actor_id)

    assert updated.version == 2
    assert [entry.action for entry in repository.audit_entries] == ["human_decision.created", "human_decision.updated"]
    assert repository.audit_entries[1].before == {
        "decision": HumanDecisionType.HOLD.value,
        "private_note": "Awaiting references",
        "version": 1,
    }
