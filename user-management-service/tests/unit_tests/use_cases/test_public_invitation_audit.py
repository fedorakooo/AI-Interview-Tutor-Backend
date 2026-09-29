from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.application.use_cases.assessments import AssessmentFlowError, PublicInvitationUseCase


class _Tokens:
    def hash(self, token: str) -> str:
        return token


class _Repository:
    def __init__(self, invitation):
        self.invitation = invitation
        self.attempt = None
        self.audit_entries = []

    async def get_invitation_by_hash_for_update(self, _token_hash):
        return self.invitation

    async def get_attempt_for_invitation(self, _invitation_id):
        return self.attempt

    async def create_attempt(self, attempt):
        self.attempt = attempt
        return attempt

    async def create_audit_entry(self, entry):
        self.audit_entries.append(entry)
        return entry


class _Uow:
    def __init__(self, repository):
        self.assessment_repository = repository

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None


def _invitation(*, expires_at=None):
    return SimpleNamespace(
        id=uuid4(), organization_id=uuid4(), vacancy_id=uuid4(),
        candidate_email_normalized="candidate@example.com", status="created",
        expires_at=expires_at or datetime.now(UTC) + timedelta(hours=1),
        attempts_started=0, max_attempts=1,
    )


@pytest.mark.asyncio
async def test_preflight_opens_once_and_never_records_the_secret_or_email():
    repository = _Repository(_invitation())
    use_case = PublicInvitationUseCase(_Uow(repository), _Tokens())

    await use_case.preflight("secret-is-not-persisted")
    await use_case.preflight("secret-is-not-persisted")

    assert repository.invitation.status == "opened"
    assert [entry.action for entry in repository.audit_entries] == ["invitation.opened"]
    assert repository.audit_entries[0].after is None


@pytest.mark.asyncio
async def test_expired_preflight_persists_terminal_state_before_safe_error():
    repository = _Repository(_invitation(expires_at=datetime.now(UTC) - timedelta(seconds=1)))

    with pytest.raises(AssessmentFlowError):
        await PublicInvitationUseCase(_Uow(repository), _Tokens()).preflight("expired-token")

    assert repository.invitation.status == "expired"


@pytest.mark.asyncio
async def test_start_is_idempotent_and_audits_only_the_first_attempt():
    repository = _Repository(_invitation())
    use_case = PublicInvitationUseCase(_Uow(repository), _Tokens())

    first = await use_case.start("token", "candidate@example.com", "Candidate", "privacy-v1")
    repeated = await use_case.start("token", "candidate@example.com", "Candidate", "privacy-v1")

    assert first.id == repeated.id
    assert repository.invitation.attempts_started == 1
    assert repository.invitation.status == "in_progress"
    assert [entry.action for entry in repository.audit_entries] == ["invitation.started"]
