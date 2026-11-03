from datetime import UTC, datetime

from src.app.container import AppContainer, build_container
from src.domain.enums.cv_policy import CvPolicy
from src.domain.interfaces.ai.answer_evaluator import IAnswerEvaluator
from src.domain.interfaces.ai.assessment_text_writer import IAssessmentTextWriter
from src.domain.interfaces.ai.feedback_writer import IFeedbackWriter
from src.domain.interfaces.ai.spec_drafter import ISpecDrafter
from src.domain.interfaces.repositories.attempt_data_repository import IAttemptDataRepository
from src.domain.value_objects.assessment_context import AssessmentContext
from src.domain.value_objects.candidate_cv import CandidateCv

from tests.fakes.ai import (
    FakeSpecDrafter,
    ScriptedEvaluator,
    ScriptedFeedbackWriter,
    ScriptedInterviewer,
    ScriptedTextWriter,
)
from tests.fakes.builders import build_context
from tests.fakes.clients import FakeContextClient
from tests.fakes.messaging import RecordingPublisher
from tests.fakes.repositories import (
    FakeCvRepository,
    InMemoryAssessmentRepository,
    InMemoryAttemptDataRepository,
    InMemoryCompletionOutboxRepository,
    InMemoryFeedbackRepository,
    InMemoryInterviewEventRepository,
)
from tests.fakes.session import InMemoryLock, InMemoryPresence

FIXED_NOW = datetime(2026, 11, 2, 10, 0, tzinfo=UTC)


class FakeStack:
    def __init__(
        self,
        *,
        context: AssessmentContext | None = None,
        context_error: Exception | None = None,
        cv: CandidateCv | None = CandidateCv(),
        now: datetime = FIXED_NOW,
        evaluator: IAnswerEvaluator | None = None,
        text_writer: IAssessmentTextWriter | None = None,
        feedback_writer: IFeedbackWriter | None = None,
        spec_drafter: ISpecDrafter | None = None,
        attempt_data_repository: IAttemptDataRepository | None = None,
        token_verifier=None,
    ) -> None:
        self.now = now
        self.context = context or build_context(CvPolicy.REQUIRED)
        self.event_repository = InMemoryInterviewEventRepository()
        self.assessment_repository = InMemoryAssessmentRepository()
        self.feedback_repository = InMemoryFeedbackRepository()
        self.completion_outbox_repository = InMemoryCompletionOutboxRepository()
        self.attempt_data_repository = attempt_data_repository or InMemoryAttemptDataRepository()
        self.cv_repository = FakeCvRepository(cv)
        self.lock = InMemoryLock()
        self.presence = InMemoryPresence()
        self.evaluator = evaluator or ScriptedEvaluator()
        self.interviewer = ScriptedInterviewer()
        self.text_writer = text_writer or ScriptedTextWriter()
        self.feedback_writer = feedback_writer or ScriptedFeedbackWriter()
        self.spec_drafter = spec_drafter or FakeSpecDrafter()
        self.publisher = RecordingPublisher()
        self.context_client = FakeContextClient(self.context, context_error)
        self.container: AppContainer = build_container(
            None,
            None,
            None,
            event_repository=self.event_repository,
            assessment_repository=self.assessment_repository,
            feedback_repository=self.feedback_repository,
            completion_outbox_repository=self.completion_outbox_repository,
            attempt_data_repository=self.attempt_data_repository,
            cv_repository=self.cv_repository,
            lock=self.lock,
            presence=self.presence,
            evaluator=self.evaluator,
            interviewer=self.interviewer,
            assessment_text_writer=self.text_writer,
            feedback_writer=self.feedback_writer,
            spec_drafter=self.spec_drafter,
            completed_publisher=self.publisher,
            context_client=self.context_client,
            token_verifier=token_verifier,
            clock=lambda: self.now,
        )


def completed_stack(
    *,
    context: AssessmentContext | None = None,
    complete: bool = True,
    text_writer: IAssessmentTextWriter | None = None,
    feedback_writer: IFeedbackWriter | None = None,
    now: datetime = FIXED_NOW,
) -> FakeStack:
    from dataclasses import replace

    from tests.fakes.builders import build_events

    stack = FakeStack(context=context, now=now, text_writer=text_writer, feedback_writer=feedback_writer)
    session_id = str(stack.context.attempt_id)
    source = build_events(CvPolicy.REQUIRED) if complete else build_events(CvPolicy.REQUIRED)[:-2]
    stack.event_repository.events[session_id] = [replace(event, session_id=session_id) for event in source]
    return stack
