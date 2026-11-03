import logging
from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from src.domain.entities.interview_connection import InterviewConnection
from src.domain.events.candidate_message import CandidateMessage
from src.domain.events.evidence_recorded import EvidenceRecorded
from src.domain.events.focus_coverage_changed import FocusCoverageChanged
from src.domain.events.session_event import SessionEvent
from src.domain.interfaces.ai.answer_evaluator import IAnswerEvaluator
from src.domain.interfaces.repositories.interview_event_repository import IInterviewEventRepository
from src.domain.services.evidence_builder import EvidenceBuilder
from src.domain.services.interview_planner import ASKING_KINDS, InterviewPlanner
from src.domain.services.journal_folder import JournalFolder
from src.domain.value_objects.evaluation_request import EvaluationRequest
from src.domain.value_objects.evaluation_result import EvaluationResult

logger = logging.getLogger(__name__)


class EvidenceRecorder:
    def __init__(
        self,
        event_repository: IInterviewEventRepository,
        evaluator: IAnswerEvaluator,
        clock: Callable[[], datetime],
    ) -> None:
        self._event_repository = event_repository
        self._evaluator = evaluator
        self._clock = clock

    async def record(
        self, connection: InterviewConnection, events: list[SessionEvent], answer: CandidateMessage
    ) -> None:
        state = JournalFolder.fold(events)
        question = next(
            (state.messages[seq] for seq in sorted(state.messages, reverse=True) if seq < answer.seq),
            None,
        )
        if question is None or question.role != "interviewer" or question.kind not in ASKING_KINDS:
            return

        template = connection.context.template
        planner = InterviewPlanner(template)
        focus = template.focus_by_id(question.focus_id or "")
        items = [item for item in state.evidence if item.answer_seq == answer.seq]
        covered_after = {
            event.focus_id for event in events if isinstance(event, FocusCoverageChanged) and event.seq > answer.seq
        }
        topics: tuple[str, ...] = ()
        if not items and focus.id not in covered_after:
            try:
                result = await self._evaluator.evaluate(
                    EvaluationRequest(
                        template=template, target_focus=focus, question_text=question.text, answer_text=answer.text
                    )
                )
            except Exception:
                logger.exception("Answer evaluation failed for session %s", answer.session_id)
                result = EvaluationResult(answer_was_complete=False)

            topics = result.covered_must_cover
            items = EvidenceBuilder.build(
                result.evidence, template, answer.session_id, question.seq, answer.seq, answer.text
            )
            for item in items:
                event = EvidenceRecorded(
                    event_id=uuid4(),
                    session_id=answer.session_id,
                    seq=events[-1].seq + 1,
                    occurred_at=self._clock(),
                    evidence=item,
                )
                await self._event_repository.append(event)
                events.append(event)

        state = JournalFolder.fold(events)
        touched = [focus.id] + [item.focus_id for item in items if item.focus_id != focus.id]
        for focus_id in dict.fromkeys(touched):
            if focus_id in covered_after:
                continue
            status, count, covered = planner.coverage_after_answer(
                state, focus_id, topics if focus_id == focus.id else ()
            )
            event = FocusCoverageChanged(
                event_id=uuid4(),
                session_id=answer.session_id,
                seq=events[-1].seq + 1,
                occurred_at=self._clock(),
                focus_id=focus_id,
                status=status,
                evidence_count=count,
                covered_must_cover=covered,
            )
            await self._event_repository.append(event)
            events.append(event)
