from collections.abc import Sequence

from shared_models.assessment.contracts import AssessmentTemplateSnapshot
from shared_models.assessment.evidence import Verdict
from shared_models.assessment.report import Assessment
from shared_models.assessment.session_events import SessionEvent
from shared_models.assessment.session_state import (
    InvalidEventLogError,
    SessionState,
    SessionStatus,
    fold_events,
    verify_evidence,
    verify_quote,
)


class InconsistentAssessmentError(ValueError):
    """Raised when the report disagrees with its template or journal."""


def verify_assessment(
    assessment: Assessment,
    template: AssessmentTemplateSnapshot,
    events: Sequence[SessionEvent],
) -> None:
    """Check that the report refers only to template focus areas and verified journal events."""
    try:
        state = fold_events(events)
        _verify(assessment, template, state)
    except InvalidEventLogError as exc:
        raise InconsistentAssessmentError(str(exc)) from exc


def _verify(assessment: Assessment, template: AssessmentTemplateSnapshot, state: SessionState) -> None:
    if state.status != SessionStatus.COMPLETED:
        raise InconsistentAssessmentError("Assessment requires a completed session")
    if assessment.session_id != state.session_id or assessment.attempt_id != state.attempt_id:
        raise InconsistentAssessmentError("Assessment does not belong to this session")
    if assessment.template_version != state.template_version:
        raise InconsistentAssessmentError("Assessment template_version differs from the session")

    template_ids = [focus.id for focus in template.criteria]
    report_ids = [item.focus_id for item in assessment.focus]
    if sorted(report_ids) != sorted(template_ids):
        raise InconsistentAssessmentError("Assessment must cover each template focus area exactly once")

    logged = {item.evidence_id: item for item in state.evidence}
    asked_custom: set[str] = set()
    for message in state.messages.values():
        if message.custom_question_index is None:
            continue
        if message.custom_question_index >= len(template.custom_questions):
            raise InconsistentAssessmentError(f"Unknown custom question index {message.custom_question_index}")
        custom = template.custom_questions[message.custom_question_index]
        if custom.focus_id != message.focus_id:
            raise InconsistentAssessmentError("Custom question was asked under a different focus area")
        asked_custom.add(custom.focus_id)
    for item in assessment.focus:
        focus = template.focus_by_id(item.focus_id)
        for evidence in item.evidence:
            if evidence.focus_id != item.focus_id:
                raise InconsistentAssessmentError(f"Evidence {evidence.evidence_id} is attached to the wrong focus")
            if logged.get(evidence.evidence_id) != evidence:
                raise InconsistentAssessmentError(f"Evidence {evidence.evidence_id} is not in the journal")
            verify_evidence(evidence, state.messages)
        if (len(item.evidence) < focus.min_evidence) != (item.verdict == Verdict.NOT_ASSESSED):
            raise InconsistentAssessmentError(f"{item.focus_id}: not_assessed must match min_evidence")
        covered, missed = set(item.covered_must_cover), set(item.missed_must_cover)
        if covered & missed or covered | missed != set(focus.must_cover):
            raise InconsistentAssessmentError(f"{item.focus_id}: must_cover lists do not match the template")
        if item.reference_comparison is not None and item.focus_id not in asked_custom:
            raise InconsistentAssessmentError(f"{item.focus_id}: reference comparison without a custom question")

    for finding in assessment.red_flags:
        if finding.flag not in template.red_flags:
            raise InconsistentAssessmentError(f"Unknown red flag: {finding.flag}")
        for quote in finding.quotes:
            verify_quote(quote, state.messages)

    coverage = assessment.coverage
    assessed = [item for item in assessment.focus if item.verdict != Verdict.NOT_ASSESSED]
    required_ids = {focus.id for focus in template.criteria if focus.required}
    expected = (
        len(template_ids),
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
        raise InconsistentAssessmentError(f"Coverage {actual} does not match the journal and template {expected}")
