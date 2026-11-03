from typing import Any

from shared_models.assessment import AssessmentOverview, FocusDetail

from src.domain.entities.assessment import Assessment
from src.domain.entities.focus_assessment import FocusAssessment
from src.domain.entities.session_state import SessionState
from src.domain.value_objects.evidence_item import EvidenceItem
from src.domain.value_objects.interview_template import InterviewTemplate


class ReportViewMapper:
    @staticmethod
    def overview(assessment: Assessment, template: InterviewTemplate) -> AssessmentOverview:
        focus_overviews: list[dict[str, Any]] = []
        for item in assessment.focus:
            focus = template.focus_by_id(item.focus_id)
            signals = [signal for evidence in item.evidence for signal in evidence.matched_signals]
            focus_overviews.append(
                {
                    "focus_id": item.focus_id,
                    "skill": focus.skill,
                    "required": focus.required,
                    "weight": focus.weight,
                    "verdict": item.verdict.value,
                    "final_verdict": item.final_verdict.value,
                    "confidence": item.confidence,
                    "summary_short": item.summary_short,
                    "evidence_count": len(item.evidence),
                    "matched_strong_signals": [s for s in dict.fromkeys(signals) if s in focus.strong_signals],
                    "matched_weak_signals": [s for s in dict.fromkeys(signals) if s in focus.weak_signals],
                    "covered_must_cover": list(item.covered_must_cover),
                    "missed_must_cover": list(item.missed_must_cover),
                    "reviewed": bool(item.review),
                }
            )
        return AssessmentOverview.model_validate(
            {
                "assessment_id": assessment.assessment_id,
                "attempt_id": assessment.attempt_id,
                "template_version": assessment.template_version,
                "report_version": assessment.report_version,
                "generator_version": assessment.generator_version,
                "generated_at": assessment.generated_at,
                "coverage": {
                    "focus_total": assessment.coverage.focus_total,
                    "focus_assessed": assessment.coverage.focus_assessed,
                    "required_total": assessment.coverage.required_total,
                    "required_assessed": assessment.coverage.required_assessed,
                    "questions_asked": assessment.coverage.questions_asked,
                },
                "overall_summary": assessment.overall_summary,
                "focus": focus_overviews,
                "red_flags": [{"flag": f.flag, "reasoning": f.reasoning} for f in assessment.red_flags],
            }
        )

    @staticmethod
    def focus_detail(
        assessment: Assessment, template: InterviewTemplate, state: SessionState, focus_id: str
    ) -> FocusDetail:
        item = next(candidate for candidate in assessment.focus if candidate.focus_id == focus_id)
        focus = template.focus_by_id(focus_id)
        evidence_by_question = {evidence.question_seq: evidence for evidence in item.evidence}

        question_seqs = {
            seq
            for seq, message in state.messages.items()
            if message.role == "interviewer" and message.focus_id == focus_id and message.kind is not None
        } | set(evidence_by_question)

        timeline: list[dict[str, Any]] = []
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
            evidence = evidence_by_question.get(question_seq)
            timeline.append(
                {
                    "question_seq": question_seq,
                    "question_text": question.text,
                    "answer_seq": answer.seq,
                    "answer_text": answer.text,
                    "custom_question": question.custom_question_index is not None,
                    "evidence": ReportViewMapper._evidence(evidence) if evidence else None,
                }
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
        return FocusDetail.model_validate(
            {
                "focus": ReportViewMapper._focus(item),
                "skill": focus.skill,
                "required": focus.required,
                "weight": focus.weight,
                "expected_level": focus.expected_level,
                "reference_answer": reference,
                "timeline": timeline,
            }
        )

    @staticmethod
    def _focus(item: FocusAssessment) -> dict[str, Any]:
        return {
            "focus_id": item.focus_id,
            "verdict": item.verdict.value,
            "confidence": item.confidence,
            "summary_short": item.summary_short,
            "rationale": item.rationale,
            "evidence": [ReportViewMapper._evidence(evidence) for evidence in item.evidence],
            "covered_must_cover": list(item.covered_must_cover),
            "missed_must_cover": list(item.missed_must_cover),
            "reference_comparison": item.reference_comparison,
            "review": [
                {
                    "review_id": entry.review_id,
                    "author_id": entry.author_id,
                    "created_at": entry.created_at,
                    "comment": entry.comment,
                    "manual_verdict": entry.manual_verdict.value if entry.manual_verdict else None,
                }
                for entry in item.review
            ],
        }

    @staticmethod
    def _evidence(evidence: EvidenceItem) -> dict[str, Any]:
        return {
            "evidence_id": evidence.evidence_id,
            "focus_id": evidence.focus_id,
            "question_seq": evidence.question_seq,
            "answer_seq": evidence.answer_seq,
            "level": evidence.level.value,
            "matched_signals": list(evidence.matched_signals),
            "quotes": [
                {"event_seq": quote.event_seq, "start": quote.start, "end": quote.end, "text": quote.text}
                for quote in evidence.quotes
            ],
            "reasoning": evidence.reasoning,
        }
