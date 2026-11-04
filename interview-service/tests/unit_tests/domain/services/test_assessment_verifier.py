from dataclasses import replace
from uuid import uuid4

import pytest
from src.domain.entities.assessment import Assessment
from src.domain.enums.cv_policy import CvPolicy
from src.domain.enums.verdict import Verdict
from src.domain.exceptions.report_errors import InconsistentReportError
from src.domain.services.assessment_verifier import AssessmentVerifier

from tests.fakes.builders import build_assessment, build_events, build_template

POLICIES = [CvPolicy.REQUIRED, CvPolicy.NONE]


def with_focus(assessment: Assessment, index: int, **changes: object) -> Assessment:
    focus = list(assessment.focus)
    focus[index] = replace(focus[index], **changes)
    return replace(assessment, focus=tuple(focus))


@pytest.mark.parametrize("policy", POLICIES)
class TestAssessmentVerifier:
    def test_mock_assessment_matches_template_and_journal(self, policy: CvPolicy) -> None:
        AssessmentVerifier.verify(build_assessment(policy), build_template(policy), build_events(policy))

    def test_not_assessed_differs_from_weak(self, policy: CvPolicy) -> None:
        verdicts = {item.focus_id: item.verdict for item in build_assessment(policy).focus}

        assert verdicts["testing"] == Verdict.NOT_ASSESSED
        assert verdicts["async_io"] == Verdict.WEAK

    def test_unknown_focus_id_is_rejected(self, policy: CvPolicy) -> None:
        assessment = with_focus(build_assessment(policy), 0, focus_id="ghost")

        with pytest.raises(InconsistentReportError, match="exactly once"):
            AssessmentVerifier.verify(assessment, build_template(policy), build_events(policy))

    def test_evidence_missing_from_the_journal_is_rejected(self, policy: CvPolicy) -> None:
        assessment = build_assessment(policy)
        first = assessment.focus[0].evidence
        assessment = with_focus(assessment, 0, evidence=(replace(first[0], evidence_id=uuid4()), *first[1:]))

        with pytest.raises(InconsistentReportError, match="not in the journal"):
            AssessmentVerifier.verify(assessment, build_template(policy), build_events(policy))

    def test_event_seq_out_of_the_journal_is_rejected(self, policy: CvPolicy) -> None:
        assessment = build_assessment(policy)
        finding = assessment.red_flags[0]
        quote = replace(finding.quotes[0], event_seq=9999)
        assessment = replace(assessment, red_flags=(replace(finding, quotes=(quote,)),))

        with pytest.raises(InconsistentReportError, match="not a candidate message"):
            AssessmentVerifier.verify(assessment, build_template(policy), build_events(policy))

    def test_verdict_must_match_the_computed_result(self, policy: CvPolicy) -> None:
        assessment = build_assessment(policy)
        testing = next(i for i, item in enumerate(assessment.focus) if item.focus_id == "testing")
        assessment = with_focus(assessment, testing, verdict=Verdict.WEAK)

        with pytest.raises(InconsistentReportError, match="computed result"):
            AssessmentVerifier.verify(assessment, build_template(policy), build_events(policy))

    def test_incomplete_session_is_rejected(self, policy: CvPolicy) -> None:
        with pytest.raises(InconsistentReportError, match="completed session"):
            AssessmentVerifier.verify(build_assessment(policy), build_template(policy), build_events(policy)[:-2])
