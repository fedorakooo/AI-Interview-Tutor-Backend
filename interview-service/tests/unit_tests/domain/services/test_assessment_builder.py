from datetime import UTC, datetime

import pytest
from src.application.services.report_loader import GENERATOR_VERSION
from src.domain.enums.cv_policy import CvPolicy
from src.domain.enums.verdict import Verdict
from src.domain.exceptions.report_errors import InconsistentReportError, SessionNotCompletedError
from src.domain.services.assessment_builder import AssessmentBuilder
from src.domain.services.assessment_verifier import AssessmentVerifier
from src.domain.services.journal_folder import JournalFolder
from src.domain.value_objects.red_flag_draft import RedFlagDraft

from tests.fakes.builders import build_context, build_events, build_template, build_texts

POLICY = CvPolicy.REQUIRED
TEMPLATE = build_template(POLICY)
ATTEMPT_ID = build_context(POLICY).attempt_id
NOW = datetime(2026, 11, 3, tzinfo=UTC)
FLAG = TEMPLATE.red_flags[1]


def build(events, texts):
    return AssessmentBuilder.build(ATTEMPT_ID, TEMPLATE, JournalFolder.fold(events), texts, GENERATOR_VERSION, NOW)


def test_builder_uses_model_texts_but_computes_verdicts_in_code() -> None:
    events = build_events(POLICY)
    assessment = build(events, build_texts(TEMPLATE))

    AssessmentVerifier.verify(assessment, TEMPLATE, events)
    by_id = {item.focus_id: item for item in assessment.focus}
    assert by_id["databases"].summary_short == "Summary of databases"
    assert by_id["databases"].reference_comparison == "Matches the reference."
    assert by_id["api_design"].reference_comparison is None
    assert by_id["testing"].verdict == Verdict.NOT_ASSESSED
    assert assessment.overall_summary.startswith("A solid backend")
    assert assessment.red_flags[0].quotes[0].text == "QA handles most of that on our team"


def test_builder_falls_back_to_deterministic_texts_without_a_model() -> None:
    events = build_events(POLICY)
    assessment = build(events, None)

    AssessmentVerifier.verify(assessment, TEMPLATE, events)
    assert assessment.red_flags == ()
    assert "Verdicts by focus area" in assessment.overall_summary
    assert all(item.summary_short for item in assessment.focus)


def test_builder_drops_hallucinated_red_flags() -> None:
    drafts = (
        RedFlagDraft(flag="Invented flag", quotes=("QA handles most of that on our team",), reasoning="x"),
        RedFlagDraft(flag=FLAG, quotes=("words the candidate never wrote",), reasoning="x"),
    )

    assessment = build(build_events(POLICY), build_texts(TEMPLATE, red_flags=drafts))

    assert assessment.red_flags == ()


def test_builder_requires_a_completed_session() -> None:
    with pytest.raises(SessionNotCompletedError):
        build(build_events(POLICY)[:-2], None)


def test_verifier_rejects_a_report_that_disagrees_with_the_journal() -> None:
    events = build_events(POLICY)
    assessment = build(events, None)

    with pytest.raises(InconsistentReportError):
        AssessmentVerifier.verify(assessment, TEMPLATE, events[:-2])
