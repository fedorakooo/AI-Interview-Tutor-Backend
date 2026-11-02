from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from shared_models.assessment.contracts import AssessmentTemplateSnapshot, CvPolicy
from shared_models.assessment.evidence import EvidenceItem, Verdict
from shared_models.assessment.report import Assessment, AssessmentCoverage, FocusAssessment
from shared_models.assessment.session_state import SessionState


class FocusOverview(BaseModel):
    focus_id: str
    skill: str
    required: bool
    weight: int
    verdict: Verdict
    final_verdict: Verdict
    confidence: float
    summary_short: str
    evidence_count: int
    matched_strong_signals: list[str] = Field(default_factory=list)
    matched_weak_signals: list[str] = Field(default_factory=list)
    covered_must_cover: list[str] = Field(default_factory=list)
    missed_must_cover: list[str] = Field(default_factory=list)
    reviewed: bool


class RedFlagOverview(BaseModel):
    flag: str
    reasoning: str


class AssessmentOverview(BaseModel):
    assessment_id: UUID
    attempt_id: UUID
    template_version: int
    report_version: int
    generator_version: str
    generated_at: datetime
    coverage: AssessmentCoverage
    overall_summary: str
    focus: list[FocusOverview]
    red_flags: list[RedFlagOverview]


class TimelineEntry(BaseModel):
    question_seq: int
    question_text: str
    answer_seq: int
    answer_text: str
    custom_question: bool
    evidence: EvidenceItem | None = None


class FocusDetail(BaseModel):
    focus: FocusAssessment
    skill: str
    required: bool
    weight: int
    expected_level: str
    reference_answer: str | None = None
    timeline: list[TimelineEntry]


class ReviewRequest(BaseModel):
    author_id: UUID
    comment: str = Field(min_length=1, max_length=2000)
    manual_verdict: Verdict | None = None


class TemplateDraftRequest(BaseModel):
    brief: str = Field(min_length=1, max_length=8000)
    job_description: str | None = Field(default=None, max_length=20000)
    title: str | None = Field(default=None, max_length=200)
    seniority: str | None = Field(default=None, max_length=64)
    language: str = Field(default="en", pattern=r"^[a-z]{2,3}(-[A-Za-z]{2,4})?$")
    cv_policy: CvPolicy = CvPolicy.REQUIRED
    candidate_feedback: bool = False


def build_overview(assessment: Assessment, template: AssessmentTemplateSnapshot) -> AssessmentOverview:
    focus_overviews: list[FocusOverview] = []
    for item in assessment.focus:
        focus = template.focus_by_id(item.focus_id)
        signals = [signal for evidence in item.evidence for signal in evidence.matched_signals]
        focus_overviews.append(
            FocusOverview(
                focus_id=item.focus_id,
                skill=focus.skill,
                required=focus.required,
                weight=focus.weight,
                verdict=item.verdict,
                final_verdict=item.final_verdict,
                confidence=item.confidence,
                summary_short=item.summary_short,
                evidence_count=len(item.evidence),
                matched_strong_signals=[s for s in dict.fromkeys(signals) if s in focus.strong_signals],
                matched_weak_signals=[s for s in dict.fromkeys(signals) if s in focus.weak_signals],
                covered_must_cover=item.covered_must_cover,
                missed_must_cover=item.missed_must_cover,
                reviewed=bool(item.review),
            )
        )
    return AssessmentOverview(
        assessment_id=assessment.assessment_id,
        attempt_id=assessment.attempt_id,
        template_version=assessment.template_version,
        report_version=assessment.report_version,
        generator_version=assessment.generator_version,
        generated_at=assessment.generated_at,
        coverage=assessment.coverage,
        overall_summary=assessment.overall_summary,
        focus=focus_overviews,
        red_flags=[RedFlagOverview(flag=f.flag, reasoning=f.reasoning) for f in assessment.red_flags],
    )


def build_focus_detail(
    assessment: Assessment,
    template: AssessmentTemplateSnapshot,
    state: SessionState,
    focus_id: str,
) -> FocusDetail:
    item = next(candidate for candidate in assessment.focus if candidate.focus_id == focus_id)
    focus = template.focus_by_id(focus_id)
    evidence_by_question = {evidence.question_seq: evidence for evidence in item.evidence}

    question_seqs = {
        seq
        for seq, message in state.messages.items()
        if message.role == "interviewer" and message.focus_id == focus_id and message.kind is not None
    } | set(evidence_by_question)

    timeline: list[TimelineEntry] = []
    for question_seq in sorted(question_seqs):
        question = state.messages[question_seq]
        answer = next(
            (
                state.messages[seq]
                for seq in sorted(state.messages)
                if seq > question_seq and state.messages[seq].role == "candidate"
            ),
            None,
        )
        if answer is None:
            continue
        timeline.append(
            TimelineEntry(
                question_seq=question_seq,
                question_text=question.text,
                answer_seq=answer.seq,
                answer_text=answer.text,
                custom_question=question.custom_question_index is not None,
                evidence=evidence_by_question.get(question_seq),
            )
        )

    reference = next(
        (
            template.custom_questions[message.custom_question_index].reference_answer
            for message in state.messages.values()
            if message.custom_question_index is not None
            and message.focus_id == focus_id
            and message.custom_question_index < len(template.custom_questions)
        ),
        None,
    )
    return FocusDetail(
        focus=item,
        skill=focus.skill,
        required=focus.required,
        weight=focus.weight,
        expected_level=focus.expected_level,
        reference_answer=reference,
        timeline=timeline,
    )
