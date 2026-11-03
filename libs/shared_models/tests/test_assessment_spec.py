from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import BaseModel, ValidationError
from shared_models.assessment import (
    Assessment,
    AssessmentContext,
    AssessmentTemplateSnapshot,
    CvPolicy,
    EvidenceRecorded,
    InconsistentAssessmentError,
    QuoteRef,
    ReviewEntry,
    RubricCriterion,
    SessionCompleted,
    SessionEventLogAdapter,
    SessionStarted,
    Verdict,
    fold_events,
    verify_assessment,
)
from shared_models.assessment.mocks import (
    mock_assessment,
    mock_assessment_context,
    mock_session_events,
    mock_template,
)
from shared_models.assessment.session_events import CandidateMessage, CompletionReason
from shared_models.assessment.session_state import InvalidEventLogError, SessionStatus

POLICIES = [CvPolicy.REQUIRED, CvPolicy.NONE]


def template_payload(**overrides: object) -> dict:
    return mock_template().model_dump(mode="json") | overrides


class TestTemplateValidation:
    def test_mock_template_is_valid(self) -> None:
        template = mock_template()

        assert template.schema_version == 2
        assert sum(focus.weight for focus in template.focus_areas) == 100

    def test_rejects_empty_focus_areas(self) -> None:
        with pytest.raises(ValidationError):
            AssessmentTemplateSnapshot.model_validate(template_payload(criteria=[]))

    def test_rejects_blank_skill(self) -> None:
        payload = template_payload()
        payload["criteria"][0]["skill"] = "   "

        with pytest.raises(ValidationError, match="must not be blank"):
            AssessmentTemplateSnapshot.model_validate(payload)

    def test_rejects_duplicate_ids(self) -> None:
        payload = template_payload()
        payload["criteria"][1]["id"] = payload["criteria"][0]["id"]

        with pytest.raises(ValidationError, match="unique"):
            AssessmentTemplateSnapshot.model_validate(payload)

    def test_rejects_weights_not_totalling_one_hundred(self) -> None:
        payload = template_payload()
        payload["criteria"][0]["weight"] = 30

        with pytest.raises(ValidationError, match="total 100"):
            AssessmentTemplateSnapshot.model_validate(payload)

    def test_requires_at_least_one_required_focus(self) -> None:
        payload = template_payload()
        for focus in payload["criteria"]:
            focus["required"] = False

        with pytest.raises(ValidationError, match="must be required"):
            AssessmentTemplateSnapshot.model_validate(payload)

    def test_rejects_custom_question_with_unknown_focus(self) -> None:
        payload = template_payload()
        payload["custom_questions"][0]["focus_id"] = "missing"

        with pytest.raises(ValidationError, match="unknown focus ids"):
            AssessmentTemplateSnapshot.model_validate(payload)

    @pytest.mark.parametrize(
        ("field", "value"),
        [("question_count", 0), ("question_count", 31), ("duration_minutes", 4)],
    )
    def test_rejects_out_of_range_limits(self, field: str, value: int) -> None:
        with pytest.raises(ValidationError):
            AssessmentTemplateSnapshot.model_validate(template_payload(**{field: value}))

    def test_rejects_min_evidence_above_max_questions(self) -> None:
        payload = template_payload()
        payload["criteria"][0]["min_evidence"] = 4
        payload["criteria"][0]["max_questions"] = 2

        with pytest.raises(ValidationError, match="min_evidence"):
            AssessmentTemplateSnapshot.model_validate(payload)


class TestV1Upcast:
    def v1_payload(self) -> dict:
        return {
            "mode": "technical",
            "question_count": 8,
            "duration_minutes": 30,
            "attempt_limit": 1,
            "criteria": [
                {"skill": "Python", "required": True, "weight": 60, "expected_level": "middle", "guidance": "Idioms"},
                {"skill": "Python", "required": False, "weight": 40, "expected_level": "junior"},
            ],
        }

    def test_v1_payload_upcasts_with_required_cv_policy(self) -> None:
        template = AssessmentTemplateSnapshot.model_validate(self.v1_payload())

        assert template.schema_version == 2
        assert template.cv_policy == CvPolicy.REQUIRED
        assert [focus.id for focus in template.criteria] == ["python", "python_2"]
        assert template.criteria[0].what_to_learn == "Idioms"
        assert template.criteria[1].what_to_learn == "Python"
        assert template.custom_questions == []

    def test_upcast_is_deterministic(self) -> None:
        first = AssessmentTemplateSnapshot.model_validate(self.v1_payload())
        second = AssessmentTemplateSnapshot.model_validate(self.v1_payload())

        assert first == second

    def test_python_v1_construction_with_rubric_criterion_instances(self) -> None:
        template = AssessmentTemplateSnapshot(
            mode="technical",
            question_count=5,
            duration_minutes=20,
            attempt_limit=1,
            criteria=[RubricCriterion(skill="SQL", required=True, weight=100, expected_level="senior")],
        )

        assert template.criteria[0].id == "sql"

    def test_explicit_v2_requires_ids(self) -> None:
        payload = self.v1_payload() | {"schema_version": 2}

        with pytest.raises(ValidationError):
            AssessmentTemplateSnapshot.model_validate(payload)


class TestAssessmentContext:
    def test_none_policy_allows_missing_cv_reference(self) -> None:
        context = mock_assessment_context(CvPolicy.NONE)

        assert context.cv_correlation_id is None
        assert context.cv_policy == CvPolicy.NONE

    def test_required_policy_needs_cv_reference(self) -> None:
        payload = mock_assessment_context(CvPolicy.REQUIRED).model_dump(mode="json")
        payload["cv_correlation_id"] = None

        with pytest.raises(ValidationError, match="cv_correlation_id"):
            AssessmentContext.model_validate(payload)

    def test_legacy_context_payload_is_still_accepted(self) -> None:
        context = AssessmentContext.model_validate(
            {
                "attempt_id": str(uuid4()),
                "organization_id": str(uuid4()),
                "vacancy_id": str(uuid4()),
                "invitation_id": str(uuid4()),
                "template_version": 1,
                "template": {
                    "mode": "technical",
                    "question_count": 5,
                    "duration_minutes": 20,
                    "attempt_limit": 1,
                    "criteria": [{"skill": "SQL", "required": True, "weight": 100, "expected_level": "senior"}],
                },
                "cv_correlation_id": str(uuid4()),
            }
        )

        assert context.cv_policy == CvPolicy.REQUIRED
        assert context.job_description is None

    def test_policy_must_match_template(self) -> None:
        payload = mock_assessment_context(CvPolicy.NONE).model_dump(mode="json")
        payload["cv_policy"] = "optional"

        with pytest.raises(ValidationError, match="must match"):
            AssessmentContext.model_validate(payload)


@pytest.mark.parametrize("policy", POLICIES)
class TestSessionFold:
    def test_fold_of_completed_mock_session(self, policy: CvPolicy) -> None:
        state = fold_events(mock_session_events(policy))

        assert state.status == SessionStatus.COMPLETED
        assert state.completion_reason == CompletionReason.QUESTION_BUDGET
        assert state.questions_asked == mock_template(policy).question_count
        assert state.cv_attached is (policy != CvPolicy.NONE)
        assert len(state.evidence) == 9
        assert state.coverage["testing"].evidence_count == 1

    def test_seq_is_monotonic(self, policy: CvPolicy) -> None:
        seqs = [event.seq for event in mock_session_events(policy)]

        assert seqs == sorted(set(seqs))

    def test_intro_turn_is_not_counted_and_not_evidence(self, policy: CvPolicy) -> None:
        events = mock_session_events(policy)
        state = fold_events(events)
        intro = [m for m in state.messages.values() if m.kind == "intro"]

        assert len(intro) == (1 if policy == CvPolicy.NONE else 0)
        assert all(item.question_seq not in {m.seq for m in intro} for item in state.evidence)

    def test_rejects_events_after_terminal(self, policy: CvPolicy) -> None:
        events = mock_session_events(policy)
        late = events[-1].model_copy(update={"seq": events[-1].seq + 1, "event_id": uuid4()})

        with pytest.raises(InvalidEventLogError, match="terminal"):
            fold_events([*events, late])

    def test_rejects_non_monotonic_seq(self, policy: CvPolicy) -> None:
        events = mock_session_events(policy)
        events[3] = events[3].model_copy(update={"seq": events[2].seq})

        with pytest.raises(InvalidEventLogError, match="monotonically"):
            fold_events(events)

    def test_event_log_must_start_with_session_started(self, policy: CvPolicy) -> None:
        with pytest.raises(InvalidEventLogError, match="start with SessionStarted"):
            fold_events(mock_session_events(policy)[1:])


@pytest.mark.parametrize("policy", POLICIES)
class TestQuoteVerification:
    def test_every_quote_matches_its_message(self, policy: CvPolicy) -> None:
        events = mock_session_events(policy)
        messages = {event.seq: event.text for event in events if isinstance(event, CandidateMessage)}
        quotes = [q for event in events if isinstance(event, EvidenceRecorded) for q in event.evidence.quotes]

        assert quotes
        assert all(messages[q.event_seq][q.start : q.end] == q.text for q in quotes)

    def test_evidence_with_unverifiable_quote_is_rejected(self, policy: CvPolicy) -> None:
        events = mock_session_events(policy)
        index = next(i for i, event in enumerate(events) if isinstance(event, EvidenceRecorded))
        original = events[index].evidence
        quote = original.quotes[0]
        forged = QuoteRef(event_seq=quote.event_seq, start=quote.start + 1, end=quote.end + 1, text=quote.text)
        events[index] = events[index].model_copy(update={"evidence": original.model_copy(update={"quotes": [forged]})})

        with pytest.raises(InvalidEventLogError, match="does not match"):
            fold_events(events)

    def test_quote_must_reference_candidate_message(self, policy: CvPolicy) -> None:
        events = mock_session_events(policy)
        index = next(i for i, event in enumerate(events) if isinstance(event, EvidenceRecorded))
        original = events[index].evidence
        interviewer_seq = original.question_seq
        quote = QuoteRef(event_seq=interviewer_seq, start=0, end=3, text="abc")
        events[index] = events[index].model_copy(update={"evidence": original.model_copy(update={"quotes": [quote]})})

        with pytest.raises(InvalidEventLogError, match="not a candidate message"):
            fold_events(events)

    def test_quote_model_rejects_inconsistent_span(self, policy: CvPolicy) -> None:
        with pytest.raises(ValidationError):
            QuoteRef(event_seq=1, start=0, end=5, text="abc")


@pytest.mark.parametrize("policy", POLICIES)
class TestAssessmentConsistency:
    def test_mock_assessment_matches_template_and_journal(self, policy: CvPolicy) -> None:
        verify_assessment(mock_assessment(policy), mock_template(policy), mock_session_events(policy))

    def test_not_assessed_differs_from_weak(self, policy: CvPolicy) -> None:
        verdicts = {item.focus_id: item.verdict for item in mock_assessment(policy).focus}

        assert verdicts["testing"] == Verdict.NOT_ASSESSED
        assert verdicts["async_io"] == Verdict.WEAK

    def test_unknown_focus_id_is_rejected(self, policy: CvPolicy) -> None:
        assessment = mock_assessment(policy)
        assessment.focus[0] = assessment.focus[0].model_copy(update={"focus_id": "ghost"})

        with pytest.raises(InconsistentAssessmentError, match="exactly once"):
            verify_assessment(assessment, mock_template(policy), mock_session_events(policy))

    def test_evidence_missing_from_journal_is_rejected(self, policy: CvPolicy) -> None:
        assessment = mock_assessment(policy)
        item = assessment.focus[0].evidence[0]
        assessment.focus[0].evidence[0] = item.model_copy(update={"evidence_id": uuid4()})

        with pytest.raises(InconsistentAssessmentError, match="not in the journal"):
            verify_assessment(assessment, mock_template(policy), mock_session_events(policy))

    def test_event_seq_out_of_journal_is_rejected(self, policy: CvPolicy) -> None:
        assessment = mock_assessment(policy)
        finding = assessment.red_flags[0]
        quote = finding.quotes[0].model_copy(update={"event_seq": 9999})
        assessment.red_flags[0] = finding.model_copy(update={"quotes": [quote]})

        with pytest.raises(InconsistentAssessmentError, match="not a candidate message"):
            verify_assessment(assessment, mock_template(policy), mock_session_events(policy))

    def test_verdict_must_match_the_computed_result(self, policy: CvPolicy) -> None:
        assessment = mock_assessment(policy)
        testing = next(i for i, item in enumerate(assessment.focus) if item.focus_id == "testing")
        assessment.focus[testing] = assessment.focus[testing].model_copy(update={"verdict": Verdict.WEAK})

        with pytest.raises(InconsistentAssessmentError, match="computed result"):
            verify_assessment(assessment, mock_template(policy), mock_session_events(policy))

    def test_incomplete_session_is_rejected(self, policy: CvPolicy) -> None:
        events = mock_session_events(policy)

        with pytest.raises(InconsistentAssessmentError, match="completed session"):
            verify_assessment(mock_assessment(policy), mock_template(policy), events[:-2])


class TestReview:
    def test_final_verdict_is_last_manual_override_else_ai(self) -> None:
        focus = mock_assessment().focus[3]
        assert focus.final_verdict == Verdict.WEAK

        def entry(verdict: Verdict | None) -> ReviewEntry:
            return ReviewEntry(
                review_id=uuid4(),
                author_id=uuid4(),
                created_at=datetime(2026, 11, 3, tzinfo=UTC),
                comment="note",
                manual_verdict=verdict,
            )

        reviewed = focus.model_copy(update={"review": [entry(Verdict.ADEQUATE), entry(None)]})
        assert reviewed.verdict == Verdict.WEAK
        assert reviewed.final_verdict == Verdict.ADEQUATE

        overridden = focus.model_copy(update={"review": [*reviewed.review, entry(Verdict.STRONG)]})
        assert overridden.final_verdict == Verdict.STRONG


def _round_trip(model: BaseModel) -> BaseModel:
    return type(model).model_validate_json(model.model_dump_json())


@pytest.mark.parametrize("policy", POLICIES)
class TestJsonRoundTrip:
    def test_template(self, policy: CvPolicy) -> None:
        template = mock_template(policy)

        assert _round_trip(template) == template

    def test_context(self, policy: CvPolicy) -> None:
        context = mock_assessment_context(policy)

        assert _round_trip(context) == context

    def test_assessment(self, policy: CvPolicy) -> None:
        assessment = mock_assessment(policy)

        assert _round_trip(assessment) == assessment
        assert Assessment.model_validate_json(assessment.model_dump_json()).focus[0].final_verdict == Verdict.STRONG

    def test_event_log_discriminated_union(self, policy: CvPolicy) -> None:
        events = mock_session_events(policy)
        restored = SessionEventLogAdapter.validate_json(SessionEventLogAdapter.dump_json(events))

        assert restored == events
        assert isinstance(restored[0], SessionStarted)
        assert isinstance(restored[-1], SessionCompleted)

    def test_folded_state(self, policy: CvPolicy) -> None:
        state = fold_events(mock_session_events(policy))

        assert _round_trip(state) == state
