from pydantic_ai.models.test import TestModel
from src.agents.spec_drafter.agent import SpecDrafter
from src.agents.spec_drafter.prompts import render_request
from src.domain.enums.cv_policy import CvPolicy
from src.domain.value_objects.draft_brief import DraftBrief

REQUEST = DraftBrief(
    brief="I want to know how they debug production problems and whether they write tests.",
    job_description="Python backend developer",
    title="Backend developer",
    seniority="middle",
    language="en",
    cv_policy=CvPolicy.OPTIONAL,
    candidate_feedback=True,
)


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
    drafter = SpecDrafter([], model=TestModel(custom_output_args=output))

    draft = await drafter.draft(REQUEST)

    assert draft.focus_areas[0].skill == "Debugging" and draft.question_count == 8
