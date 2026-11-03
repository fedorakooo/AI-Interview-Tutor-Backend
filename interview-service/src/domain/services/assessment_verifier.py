from collections.abc import Sequence

from src.domain.entities.assessment import Assessment
from src.domain.entities.session_state import SessionState
from src.domain.enums.session_status import SessionStatus
from src.domain.enums.verdict import Verdict
from src.domain.events.session_event import SessionEvent
from src.domain.exceptions.report_errors import InconsistentReportError
from src.domain.exceptions.session_errors import InconsistentJournalError
from src.domain.services.evidence_verifier import EvidenceVerifier
from src.domain.services.focus_verdict_calculator import FocusVerdictCalculator
from src.domain.services.journal_folder import JournalFolder
from src.domain.value_objects.interview_template import InterviewTemplate


class AssessmentVerifier:
    @staticmethod
    def verify(assessment: Assessment, template: InterviewTemplate, events: Sequence[SessionEvent]) -> None:
        try:
            AssessmentVerifier._verify(assessment, template, JournalFolder.fold(events))
        except InconsistentJournalError as exc:
            raise InconsistentReportError(str(exc)) from exc

    @staticmethod
    def _verify(assessment: Assessment, template: InterviewTemplate, state: SessionState) -> None:
        if state.status != SessionStatus.COMPLETED:
            raise InconsistentReportError("Assessment requires a completed session")
        if assessment.session_id != state.session_id or assessment.attempt_id != state.attempt_id:
            raise InconsistentReportError("Assessment does not belong to this session")
        if assessment.template_version != state.template_version:
            raise InconsistentReportError("Assessment template_version differs from the session")

        template_ids = [focus.id for focus in template.criteria]
        report_ids = [item.focus_id for item in assessment.focus]
        if sorted(report_ids) != sorted(template_ids):
            raise InconsistentReportError("Assessment must cover each template focus area exactly once")

        logged = {item.evidence_id: item for item in state.evidence}
        asked_custom = AssessmentVerifier._asked_custom_focus_ids(template, state)
        for item in assessment.focus:
            focus = template.focus_by_id(item.focus_id)
            for evidence in item.evidence:
                if evidence.focus_id != item.focus_id:
                    raise InconsistentReportError(f"Evidence {evidence.evidence_id} is attached to the wrong focus")
                if logged.get(evidence.evidence_id) != evidence:
                    raise InconsistentReportError(f"Evidence {evidence.evidence_id} is not in the journal")
                EvidenceVerifier.verify_evidence(evidence, state.messages)
            expected_verdict, expected_confidence = FocusVerdictCalculator.compute(focus, item.evidence)
            if (item.verdict, item.confidence) != (expected_verdict, expected_confidence):
                raise InconsistentReportError(f"{item.focus_id}: verdict does not match the computed result")
            covered, missed = set(item.covered_must_cover), set(item.missed_must_cover)
            if covered & missed or covered | missed != set(focus.must_cover):
                raise InconsistentReportError(f"{item.focus_id}: must_cover lists do not match the template")
            if item.reference_comparison is not None and item.focus_id not in asked_custom:
                raise InconsistentReportError(f"{item.focus_id}: reference comparison without a custom question")

        for finding in assessment.red_flags:
            if finding.flag not in template.red_flags:
                raise InconsistentReportError(f"Unknown red flag: {finding.flag}")
            for quote in finding.quotes:
                EvidenceVerifier.verify_quote(quote, state.messages)

        AssessmentVerifier._verify_coverage(assessment, template, state)

    @staticmethod
    def _asked_custom_focus_ids(template: InterviewTemplate, state: SessionState) -> set[str]:
        asked: set[str] = set()
        for message in state.messages.values():
            if message.custom_question_index is None:
                continue
            if message.custom_question_index >= len(template.custom_questions):
                raise InconsistentReportError(f"Unknown custom question index {message.custom_question_index}")
            custom = template.custom_questions[message.custom_question_index]
            if custom.focus_id != message.focus_id:
                raise InconsistentReportError("Custom question was asked under a different focus area")
            asked.add(custom.focus_id)
        return asked

    @staticmethod
    def _verify_coverage(assessment: Assessment, template: InterviewTemplate, state: SessionState) -> None:
        coverage = assessment.coverage
        assessed = [item for item in assessment.focus if item.verdict != Verdict.NOT_ASSESSED]
        required_ids = {focus.id for focus in template.criteria if focus.required}
        expected = (
            len(template.criteria),
            len(assessed),
            len(required_ids),
            len([item for item in assessed if item.focus_id in required_ids]),
            state.questions_asked,
        )
        actual = (
            coverage.focus_total,
            coverage.focus_assessed,
            coverage.required_total,
            coverage.required_assessed,
            coverage.questions_asked,
        )
        if expected != actual:
            raise InconsistentReportError(f"Coverage {actual} does not match the journal and template {expected}")
