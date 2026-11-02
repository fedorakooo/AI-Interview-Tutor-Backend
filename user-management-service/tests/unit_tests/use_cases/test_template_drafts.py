from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from shared_models.assessment import AssessmentMode, AssessmentTemplateSnapshot, CvPolicy, TemplateDraftRequest
from shared_models.assessment.contracts import RubricCriterion
from src.application.use_cases.template_drafts import GenerateTemplateDraftUseCase
from src.domain.exceptions.interview_report_errors import InterviewReportUnavailableError
from src.domain.exceptions.not_found_error import NotFoundError
from src.domain.interfaces.reports.interview_spec_client import IInterviewSpecClient
from src.infrastructure.interview_service.spec_client import InterviewServiceSpecClient

DRAFT = AssessmentTemplateSnapshot(
    mode=AssessmentMode.TECHNICAL,
    question_count=5,
    duration_minutes=20,
    attempt_limit=1,
    criteria=[RubricCriterion(skill="Python", required=True, weight=100, expected_level="middle")],
)


class FakeSpecClient(IInterviewSpecClient):
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.requests: list[TemplateDraftRequest] = []

    async def create_template_draft(self, request: TemplateDraftRequest) -> AssessmentTemplateSnapshot:
        self.requests.append(request)
        if self.error:
            raise self.error
        return DRAFT


class FakeVacancyRepository:
    def __init__(self, vacancy) -> None:
        self.vacancy = vacancy

    async def get_by_id_and_organization_id(self, vacancy_id, organization_id):
        if self.vacancy and self.vacancy.id == vacancy_id and self.vacancy.organization_id == organization_id:
            return self.vacancy
        return None


class FakeAssessmentRepository:
    def __init__(self) -> None:
        self.audit_entries = []

    async def create_audit_entry(self, entry):
        self.audit_entries.append(entry)
        return entry


class FakeUow:
    def __init__(self, vacancy) -> None:
        self.vacancy_repository = FakeVacancyRepository(vacancy)
        self.assessment_repository = FakeAssessmentRepository()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None


def vacancy():
    return SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
        title="Backend",
        job_description="Build APIs",
        seniority="middle",
        language="ru",
    )


@pytest.mark.asyncio
async def test_draft_request_combines_the_recruiter_text_with_the_vacancy_and_is_audited():
    record, client, actor = vacancy(), FakeSpecClient(), uuid4()
    uow = FakeUow(record)

    draft = await GenerateTemplateDraftUseCase(uow, client)(
        record.organization_id, record.id, actor, "Check debugging skills", None, CvPolicy.NONE, True
    )

    request = client.requests[0]
    assert draft == DRAFT
    assert (request.brief, request.job_description, request.title, request.seniority) == (
        "Check debugging skills",
        "Build APIs",
        "Backend",
        "middle",
    )
    assert (request.language, request.cv_policy, request.candidate_feedback) == ("ru", CvPolicy.NONE, True)
    [entry] = uow.assessment_repository.audit_entries
    assert (entry.action, entry.actor_id, entry.vacancy_id, entry.after) == (
        "template.draft_generated",
        actor,
        record.id,
        {"focus_areas": 1},
    )
    assert "Check debugging skills" not in str(entry.after)


@pytest.mark.asyncio
async def test_explicit_language_overrides_the_vacancy_language():
    record, client = vacancy(), FakeSpecClient()

    await GenerateTemplateDraftUseCase(FakeUow(record), client)(
        record.organization_id, record.id, uuid4(), "brief", "en", CvPolicy.REQUIRED, False
    )

    assert client.requests[0].language == "en"


@pytest.mark.asyncio
async def test_vacancy_of_another_organization_is_not_found_and_nothing_is_requested():
    record, client = vacancy(), FakeSpecClient()

    with pytest.raises(NotFoundError):
        await GenerateTemplateDraftUseCase(FakeUow(record), client)(
            uuid4(), record.id, uuid4(), "brief", None, CvPolicy.REQUIRED, False
        )
    assert client.requests == []


@pytest.mark.asyncio
async def test_failed_generation_is_not_audited():
    record = vacancy()
    uow = FakeUow(record)

    with pytest.raises(InterviewReportUnavailableError):
        await GenerateTemplateDraftUseCase(uow, FakeSpecClient(InterviewReportUnavailableError()))(
            record.organization_id, record.id, uuid4(), "brief", None, CvPolicy.REQUIRED, False
        )
    assert uow.assessment_repository.audit_entries == []


@pytest.mark.asyncio
async def test_spec_client_posts_the_request_and_parses_the_template():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path, request.headers["X-Internal-Service-Token"], request.content))
        return httpx.Response(200, content=DRAFT.model_dump_json())

    client = InterviewServiceSpecClient(
        "http://interview-service:8001", "secret", transport=httpx.MockTransport(handler)
    )

    result = await client.create_template_draft(TemplateDraftRequest(brief="Check debugging"))

    assert result == DRAFT
    method, path, token, content = seen[0]
    assert (method, path, token) == ("POST", "/api/internal/spec-drafts", "secret")
    assert b"Check debugging" in content


@pytest.mark.asyncio
async def test_spec_client_maps_failures_to_unavailable():
    client = InterviewServiceSpecClient(
        "http://interview-service:8001", "secret", transport=httpx.MockTransport(lambda request: httpx.Response(502))
    )

    with pytest.raises(InterviewReportUnavailableError):
        await client.create_template_draft(TemplateDraftRequest(brief="x"))


@pytest.mark.asyncio
@pytest.mark.parametrize("vacancy_language", ["English", "EN", "e"])
async def test_a_vacancy_language_that_is_not_a_code_gives_a_domain_error_instead_of_a_crash(vacancy_language):
    from src.application.use_cases.template_drafts import InvalidDraftRequestError

    record, client = vacancy(), FakeSpecClient()
    record.language = vacancy_language

    with pytest.raises(InvalidDraftRequestError):
        await GenerateTemplateDraftUseCase(FakeUow(record), client)(
            record.organization_id, record.id, uuid4(), "brief", None, CvPolicy.REQUIRED, False
        )
    assert client.requests == []

    await GenerateTemplateDraftUseCase(FakeUow(record), client)(
        record.organization_id, record.id, uuid4(), "brief", "en", CvPolicy.REQUIRED, False
    )
    assert client.requests[0].language == "en"
