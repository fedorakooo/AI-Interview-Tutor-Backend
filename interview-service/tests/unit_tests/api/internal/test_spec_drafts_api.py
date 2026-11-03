import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from shared_models.assessment import AssessmentTemplateSnapshot, CvPolicy, TemplateDraftRequest
from src.api.exception_handler import exception_container
from src.api.internal.router import router as internal_router
from src.config import settings
from src.domain.value_objects.draft_focus import DraftFocus
from src.domain.value_objects.spec_draft import SpecDraft

from tests.fakes.ai import FakeSpecDrafter
from tests.fakes.stack import FakeStack

REQUEST = TemplateDraftRequest(
    brief="I want to know how they debug production problems and whether they write tests.",
    job_description="Python backend developer",
    title="Backend developer",
    seniority="middle",
    language="en",
    cv_policy=CvPolicy.OPTIONAL,
    candidate_feedback=True,
)


def focus(skill: str, weight: int = 10) -> DraftFocus:
    return DraftFocus(skill=skill, weight=weight)


TOKEN = "internal-secret"


def api(draft: SpecDraft | Exception) -> TestClient:
    app = FastAPI()
    app.include_router(internal_router)
    exception_container(app)
    app.state.container = FakeStack(spec_drafter=FakeSpecDrafter(draft)).container
    return TestClient(app, headers={"X-Internal-Service-Token": TOKEN})


@pytest.fixture(autouse=True)
def internal_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "internal_service_token", TOKEN)


def test_internal_api_returns_a_valid_template() -> None:
    response = api(SpecDraft(focus_areas=(focus("Python"),))).post(
        "/api/internal/spec-drafts", json=REQUEST.model_dump(mode="json")
    )

    assert response.status_code == 200
    assert AssessmentTemplateSnapshot.model_validate(response.json()).brief == REQUEST.brief


def test_internal_api_reports_unusable_and_failed_drafts() -> None:
    payload = REQUEST.model_dump(mode="json")

    assert api(SpecDraft()).post("/api/internal/spec-drafts", json=payload).status_code == 422
    assert api(RuntimeError("model down")).post("/api/internal/spec-drafts", json=payload).status_code == 502
    assert api(SpecDraft()).post("/api/internal/spec-drafts", json={"brief": ""}).status_code == 422


def test_internal_api_requires_the_service_token() -> None:
    client = api(SpecDraft(focus_areas=(focus("Python"),)))
    client.headers.pop("X-Internal-Service-Token")

    assert client.post("/api/internal/spec-drafts", json=REQUEST.model_dump(mode="json")).status_code == 401
