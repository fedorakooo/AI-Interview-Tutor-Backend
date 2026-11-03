from datetime import datetime
from uuid import UUID, uuid5

from src.domain.entities.assessment import Assessment
from src.domain.entities.focus_assessment import FocusAssessment
from src.domain.entities.session_state import SessionState
from src.domain.enums.session_status import SessionStatus
from src.domain.enums.verdict import Verdict
from src.domain.exceptions.report_errors import SessionNotCompletedError
from src.domain.services.focus_verdict_calculator import FocusVerdictCalculator
from src.domain.value_objects.assessment_coverage import AssessmentCoverage
from src.domain.value_objects.assessment_texts import AssessmentTexts
from src.domain.value_objects.interview_template import InterviewTemplate
from src.domain.value_objects.quote_ref import QuoteRef
from src.domain.value_objects.red_flag_finding import RedFlagFinding

REPORT_NAMESPACE = UUID("5b1f0c9e-7a3d-4c2b-8e6f-0d9a1b2c3d4e")
FALLBACK_SUMMARY = "Not enough evidence was collected to assess this focus area."


class AssessmentBuilder:
    @staticmethod
    def build(
        attempt_id: UUID,
        template: InterviewTemplate,
        state: SessionState,
        texts: AssessmentTexts | None,
        generator_version: str,
        generated_at: datetime,
        report_version: int = 1,
    ) -> Assessment:
        if state.status != SessionStatus.COMPLETED:
            raise SessionNotCompletedError()

        focus_texts = {item.focus_id: item for item in texts.focus} if texts else {}
        asked_custom = {
            template.custom_questions[message.custom_question_index].focus_id
            for message in state.messages.values()
            if message.custom_question_index is not None
            and message.custom_question_index < len(template.custom_questions)
        }

        focus_assessments: list[FocusAssessment] = []
        for focus in template.criteria:
            evidence = [item for item in state.evidence if item.focus_id == focus.id]
            verdict, confidence = FocusVerdictCalculator.compute(focus, evidence)
            covered = state.coverage[focus.id].covered_must_cover if focus.id in state.coverage else ()
            text = focus_texts.get(focus.id)
            reasoning = " ".join(item.reasoning for item in evidence)
            comparison = text.reference_comparison if text and focus.id in asked_custom else None
            focus_assessments.append(
                FocusAssessment(
                    focus_id=focus.id,
                    verdict=verdict,
                    confidence=confidence,
                    summary_short=(text.summary_short if text else (reasoning or FALLBACK_SUMMARY))[:200],
                    rationale=(text.rationale if text else (reasoning or FALLBACK_SUMMARY))[:3000],
                    evidence=tuple(evidence),
                    covered_must_cover=tuple(covered),
                    missed_must_cover=tuple(topic for topic in focus.must_cover if topic not in covered),
                    reference_comparison=comparison,
                )
            )

        assessed = [item for item in focus_assessments if item.verdict != Verdict.NOT_ASSESSED]
        required_ids = {focus.id for focus in template.criteria if focus.required}
        return Assessment(
            assessment_id=uuid5(REPORT_NAMESPACE, f"{state.session_id}/{report_version}/{generator_version}"),
            attempt_id=attempt_id,
            session_id=state.session_id,
            template_version=state.template_version,
            report_version=report_version,
            generator_version=generator_version,
            generated_at=generated_at,
            coverage=AssessmentCoverage(
                focus_total=len(template.criteria),
                focus_assessed=len(assessed),
                required_total=len(required_ids),
                required_assessed=len([item for item in assessed if item.focus_id in required_ids]),
                questions_asked=state.questions_asked,
            ),
            overall_summary=(
                texts.overall_summary if texts else AssessmentBuilder._fallback_overall(focus_assessments)
            )[:3000],
            focus=tuple(focus_assessments),
            red_flags=tuple(AssessmentBuilder._verified_red_flags(template, state, texts)),
        )

    @staticmethod
    def _fallback_overall(focus_assessments: list[FocusAssessment]) -> str:
        parts = [f"{item.focus_id}: {item.verdict.value}" for item in focus_assessments]
        return "Automatic summary unavailable. Verdicts by focus area: " + "; ".join(parts) + "."

    @staticmethod
    def _verified_red_flags(
        template: InterviewTemplate, state: SessionState, texts: AssessmentTexts | None
    ) -> list[RedFlagFinding]:
        findings: list[RedFlagFinding] = []
        if texts is None:
            return findings
        candidate_messages = [message for message in state.messages.values() if message.role == "candidate"]
        for draft in texts.red_flags:
            if draft.flag not in template.red_flags:
                continue
            quotes: list[QuoteRef] = []
            for candidate in draft.quotes[:5]:
                text = candidate.strip()
                for message in candidate_messages:
                    start = message.text.find(text) if text else -1
                    if start >= 0:
                        quotes.append(QuoteRef(event_seq=message.seq, start=start, end=start + len(text), text=text))
                        break
            if quotes:
                findings.append(RedFlagFinding(flag=draft.flag, quotes=tuple(quotes), reasoning=draft.reasoning[:1000]))
        return findings
