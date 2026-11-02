from dataclasses import dataclass
from datetime import timedelta

from shared_models.assessment import AssessmentTemplateSnapshot, FocusArea
from shared_models.assessment.session_events import CompletionReason, CoverageStatus, MessageKind
from shared_models.assessment.session_state import FocusCoverage, MessageRecord, SessionState

ASKING_KINDS = (MessageKind.QUESTION, MessageKind.FOLLOW_UP)


@dataclass(frozen=True)
class AskIntro:
    pass


@dataclass(frozen=True)
class AskFocus:
    focus_id: str
    kind: MessageKind
    custom_question_index: int | None = None


@dataclass(frozen=True)
class Complete:
    reason: CompletionReason


NextAction = AskIntro | AskFocus | Complete


class InterviewEngine:
    """Plan the interview deterministically without calling a language model."""

    def __init__(self, template: AssessmentTemplateSnapshot) -> None:
        self._template = template

    def next_action(self, state: SessionState, elapsed: timedelta) -> NextAction:
        if not state.cv_attached and not self._intro_asked(state):
            return AskIntro()
        if state.questions_asked >= self._template.question_count:
            return Complete(CompletionReason.QUESTION_BUDGET)
        if elapsed >= timedelta(minutes=self._template.duration_minutes):
            return Complete(CompletionReason.TIME_BUDGET)

        candidates = [
            (self._priority(focus, index, state), focus, custom_index)
            for index, focus in enumerate(self._template.criteria)
            if (custom_index := self._pending_custom_question(focus, state)) is not None or self._is_open(focus, state)
        ]
        if not candidates:
            return Complete(CompletionReason.ALL_COVERED)

        _, focus, custom_index = min(candidates, key=lambda candidate: candidate[0])
        asked = self.questions_asked_for(focus.id, state)
        kind = MessageKind.QUESTION if asked == 0 else MessageKind.FOLLOW_UP
        return AskFocus(focus_id=focus.id, kind=kind, custom_question_index=custom_index)

    def coverage_after_answer(
        self, state: SessionState, focus_id: str, covered_topics: list[str]
    ) -> tuple[CoverageStatus, int, list[str]]:
        focus = self._template.focus_by_id(focus_id)
        previous = state.coverage.get(focus_id)
        covered = list(previous.covered_must_cover) if previous else []
        for topic in covered_topics:
            if topic in focus.must_cover and topic not in covered:
                covered.append(topic)
        evidence_count = len([item for item in state.evidence if item.focus_id == focus_id])
        if evidence_count >= focus.min_evidence:
            status = CoverageStatus.COVERED
        elif self.questions_asked_for(focus_id, state) >= focus.max_questions:
            status = CoverageStatus.EXHAUSTED
        else:
            status = CoverageStatus.IN_PROGRESS
        return status, evidence_count, covered

    def pending_question(self, state: SessionState) -> MessageRecord | None:
        if not state.messages:
            return None
        last = state.messages[max(state.messages)]
        if last.role == "interviewer" and last.kind != MessageKind.CLOSING:
            return last
        return None

    @staticmethod
    def questions_asked_for(focus_id: str, state: SessionState) -> int:
        return len(
            [
                message
                for message in state.messages.values()
                if message.role == "interviewer" and message.kind in ASKING_KINDS and message.focus_id == focus_id
            ]
        )

    @staticmethod
    def _intro_asked(state: SessionState) -> bool:
        return any(message.kind == MessageKind.INTRO for message in state.messages.values())

    def _is_open(self, focus: FocusArea, state: SessionState) -> bool:
        coverage = state.coverage.get(focus.id)
        if coverage is not None and coverage.status in (CoverageStatus.COVERED, CoverageStatus.EXHAUSTED):
            return False
        return self.questions_asked_for(focus.id, state) < focus.max_questions

    def _pending_custom_question(self, focus: FocusArea, state: SessionState) -> int | None:
        if self.questions_asked_for(focus.id, state) >= focus.max_questions:
            return None
        asked = {
            message.custom_question_index
            for message in state.messages.values()
            if message.custom_question_index is not None
        }
        for index, question in enumerate(self._template.custom_questions):
            if (
                question.focus_id == focus.id
                and index not in asked
                and (question.required or self._is_open(focus, state))
            ):
                return index
        return None

    def _priority(self, focus: FocusArea, index: int, state: SessionState) -> tuple[int, int, int, int, int]:
        coverage = state.coverage.get(focus.id, FocusCoverage(focus_id=focus.id))
        required_custom = any(
            question.focus_id == focus.id and question.required for question in self._template.custom_questions
        )
        deficit = focus.min_evidence - coverage.evidence_count
        return (
            0 if required_custom and self._pending_custom_question(focus, state) is not None else 1,
            0 if focus.required else 1,
            -deficit,
            -focus.weight,
            index,
        )
