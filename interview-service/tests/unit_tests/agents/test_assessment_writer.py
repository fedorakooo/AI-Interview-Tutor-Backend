from pydantic_ai.models.test import TestModel
from src.agents.assessment_writer.agent import AssessmentTextWriter
from src.agents.assessment_writer.prompts import render_digest
from src.domain.enums.cv_policy import CvPolicy
from src.domain.enums.verdict import Verdict
from src.domain.services.journal_folder import JournalFolder
from src.domain.value_objects.assessment_digest import AssessmentDigest

from tests.fakes.builders import build_events, build_template

POLICY = CvPolicy.REQUIRED
TEMPLATE = build_template(POLICY)
FLAG = TEMPLATE.red_flags[1]


def digest() -> AssessmentDigest:
    state = JournalFolder.fold(build_events(POLICY))
    return AssessmentDigest(TEMPLATE, state, {focus.id: (Verdict.WEAK, 0.5) for focus in TEMPLATE.criteria})


def test_digest_contains_reference_answers_for_the_writer_only_and_no_email() -> None:
    rendered = render_digest(digest())

    assert "Reference answer: Read the plan with EXPLAIN" in rendered
    assert "Candidate answer: First I'd get the actual plan" in rendered
    assert "Alex Candidate" not in rendered and "@" not in rendered
    assert FLAG in rendered


async def test_assessment_agent_returns_structured_texts_without_a_network() -> None:
    output = {
        "overall_summary": "Summary",
        "focus": [{"focus_id": "databases", "summary_short": "Short", "rationale": "Long"}],
        "red_flags": [],
    }
    writer = AssessmentTextWriter([], model=TestModel(custom_output_args=output))

    result = await writer.write(digest())

    assert result.overall_summary == "Summary" and result.focus[0].focus_id == "databases"
