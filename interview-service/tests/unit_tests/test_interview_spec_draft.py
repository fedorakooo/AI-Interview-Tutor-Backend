import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic_ai.models.test import TestModel
from shared_models.assessment import AssessmentTemplateSnapshot, CvPolicy, TemplateDraftRequest
from src.api.internal.spec_drafts import router
from src.application.interview.spec_service import SpecDraftService
from src.config import settings
from src.domain.interfaces.spec_drafter import ISpecDrafter
from src.domain.interview.spec_builder import EmptySpecDraftError, build_template
from src.domain.interview.spec_dto import DraftCustomQuestion, DraftFocus, SpecDraft
from src.infrastructure.ai.spec_agent import PydanticSpecDrafter, render_request

REQUEST = TemplateDraftRequest(
    brief="I want to know how they debug production problems and whether they write tests.",
    job_description="Python backend developer",
    title="Backend developer",
    seniority="middle",
    language="en",
    cv_policy=CvPolicy.OPTIONAL,
    candidate_feedback=True,
)


def focus(skill: str, weight: int = 10, **overrides) -> DraftFocus:
    return DraftFocus(skill=skill, weight=weight, **overrides)


def test_draft_is_normalized_into_a_valid_template() -> None:
    draft = SpecDraft(
        question_count=500,
        duration_minutes=1,
        focus_areas=[
            focus(
                "Debugging production issues", 7, strong_signals=["Reads logs first"], min_evidence=9, max_questions=2
            ),
            focus("debugging production issues", 3),
            focus("Testing", 3, required=False),
            focus("  ", 5),
            focus("Python", 0),
        ],
        skip=["Frontend", "Frontend"],
    )

    template = build_template(draft, REQUEST)

    assert isinstance(template, AssessmentTemplateSnapshot)
    assert [f.id for f in template.criteria] == ["debugging_production_issues", "testing", "python"]
    assert sum(f.weight for f in template.criteria) == 100 and min(f.weight for f in template.criteria) >= 1
    assert sum(1 for f in template.criteria if f.required) == 1 and template.criteria[0].required
    assert template.question_count == 30 and template.duration_minutes == 5
    assert template.criteria[0].min_evidence == 2 == template.criteria[0].max_questions
    assert template.skip == ["Frontend"]


def test_recruiter_text_and_request_options_are_kept_verbatim() -> None:
    template = build_template(SpecDraft(focus_areas=[focus("Python")]), REQUEST)

    assert template.brief == REQUEST.brief
    assert (template.cv_policy, template.language, template.candidate_feedback) == (CvPolicy.OPTIONAL, "en", True)
    assert template.attempt_limit == 1 and template.schema_version == 2


def test_custom_questions_are_linked_by_skill_and_unknown_skills_are_dropped() -> None:
    draft = SpecDraft(
        focus_areas=[focus("SQL tuning"), focus("Python")],
        custom_questions=[
            DraftCustomQuestion(focus_skill="sql TUNING", text="Why is this query slow?", reference_answer="EXPLAIN"),
            DraftCustomQuestion(focus_skill="Rust", text="Unknown focus"),
            DraftCustomQuestion(focus_skill="Python", text="  "),
        ],
    )

    template = build_template(draft, REQUEST)

    assert [(q.focus_id, q.text, q.reference_answer) for q in template.custom_questions] == [
        ("sql_tuning", "Why is this query slow?", "EXPLAIN")
    ]


def test_weights_always_total_one_hundred() -> None:
    for weights in ([1], [1, 1, 1], [5, 0, 0, 9, 2, 7, 1], [100] * 10, [3, 3, 3]):
        draft = SpecDraft(focus_areas=[focus(f"Skill {i}", weight) for i, weight in enumerate(weights)])

        assert sum(f.weight for f in build_template(draft, REQUEST).criteria) == 100


def test_a_draft_without_usable_focus_areas_is_rejected() -> None:
    with pytest.raises(EmptySpecDraftError):
        build_template(SpecDraft(focus_areas=[focus(" ")]), REQUEST)


def test_request_rendering_includes_the_vacancy_context() -> None:
    rendered = render_request(REQUEST)

    assert REQUEST.brief in rendered and "Python backend developer" in rendered and "middle" in rendered


async def test_agent_returns_a_structured_draft_without_a_network() -> None:
    output = {
        "mode": "technical",
        "question_count": 8,
        "duration_minutes": 40,
        "focus_areas": [{"skill": "Debugging", "weight": 6, "required": True}],
    }
    drafter = PydanticSpecDrafter([], model=TestModel(custom_output_args=output))

    draft = await drafter.draft(REQUEST)

    assert draft.focus_areas[0].skill == "Debugging" and draft.question_count == 8


class FakeDrafter(ISpecDrafter):
    def __init__(self, draft: SpecDraft | Exception) -> None:
        self.draft_or_error = draft

    async def draft(self, request: TemplateDraftRequest) -> SpecDraft:
        if isinstance(self.draft_or_error, Exception):
            raise self.draft_or_error
        return self.draft_or_error


TOKEN = "internal-secret"


def api(draft: SpecDraft | Exception) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.spec_draft_service = SpecDraftService(FakeDrafter(draft))
    return TestClient(app, headers={"X-Internal-Service-Token": TOKEN})


@pytest.fixture(autouse=True)
def internal_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "internal_service_token", TOKEN)


def test_internal_api_returns_a_valid_template() -> None:
    response = api(SpecDraft(focus_areas=[focus("Python")])).post(
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
    client = api(SpecDraft(focus_areas=[focus("Python")]))
    client.headers.pop("X-Internal-Service-Token")

    assert client.post("/api/internal/spec-drafts", json=REQUEST.model_dump(mode="json")).status_code == 401
