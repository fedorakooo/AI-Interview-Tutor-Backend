from collections.abc import AsyncIterator, Callable

from src.domain.enums.evidence_level import EvidenceLevel
from src.domain.interfaces.ai.answer_evaluator import IAnswerEvaluator
from src.domain.interfaces.ai.assessment_text_writer import IAssessmentTextWriter
from src.domain.interfaces.ai.feedback_writer import IFeedbackWriter
from src.domain.interfaces.ai.interviewer_agent import IInterviewerAgent
from src.domain.interfaces.ai.spec_drafter import ISpecDrafter
from src.domain.value_objects.ask_focus import AskFocus
from src.domain.value_objects.ask_intro import AskIntro
from src.domain.value_objects.assessment_digest import AssessmentDigest
from src.domain.value_objects.assessment_texts import AssessmentTexts
from src.domain.value_objects.draft_brief import DraftBrief
from src.domain.value_objects.evaluation_request import EvaluationRequest
from src.domain.value_objects.evaluation_result import EvaluationResult
from src.domain.value_objects.evidence_draft import EvidenceDraft
from src.domain.value_objects.feedback_digest import FeedbackDigest
from src.domain.value_objects.interviewer_request import InterviewerRequest
from src.domain.value_objects.spec_draft import SpecDraft


class ScriptedEvaluator(IAnswerEvaluator):
    def __init__(self, result: Callable[[EvaluationRequest], EvaluationResult] | None = None) -> None:
        self.requests: list[EvaluationRequest] = []
        self.fail = False
        self._result = result or self._default_result

    @staticmethod
    def _default_result(request: EvaluationRequest) -> EvaluationResult:
        focus = request.target_focus
        return EvaluationResult(
            answer_was_complete=True,
            evidence=(
                EvidenceDraft(
                    focus_id=focus.id,
                    level=EvidenceLevel.STRONG,
                    matched_signals=focus.strong_signals[:1],
                    quotes=(request.answer_text[:12],),
                    reasoning="Reasonable answer.",
                ),
            ),
            covered_must_cover=focus.must_cover[:1],
        )

    async def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        self.requests.append(request)
        if self.fail:
            raise RuntimeError("model unavailable")
        return self._result(request)


class ScriptedInterviewer(IInterviewerAgent):
    def __init__(self) -> None:
        self.requests: list[InterviewerRequest] = []
        self.empty = False

    async def stream_message(self, request: InterviewerRequest) -> AsyncIterator[str]:
        self.requests.append(request)
        if self.empty:
            return
        action = request.action
        subject = (
            action.focus_id if isinstance(action, AskFocus) else "intro" if isinstance(action, AskIntro) else "end"
        )
        yield f"Question about {subject}"
        yield " please."


class ScriptedTextWriter(IAssessmentTextWriter):
    def __init__(self, texts: AssessmentTexts | None = None) -> None:
        self.texts = texts
        self.digests: list[AssessmentDigest] = []
        self.fail = False

    async def write(self, digest: AssessmentDigest) -> AssessmentTexts:
        self.digests.append(digest)
        if self.fail or self.texts is None:
            raise RuntimeError("model unavailable")
        return self.texts


class ScriptedFeedbackWriter(IFeedbackWriter):
    def __init__(self, text: str | None = "Thank you! You did well on Python fundamentals.") -> None:
        self.text = text
        self.digests: list[FeedbackDigest] = []

    async def write(self, digest: FeedbackDigest) -> str:
        self.digests.append(digest)
        if self.text is None:
            raise RuntimeError("model unavailable")
        return self.text


class FakeSpecDrafter(ISpecDrafter):
    def __init__(self, draft: SpecDraft | Exception | None = None) -> None:
        self.draft_or_error = draft if draft is not None else SpecDraft()

    async def draft(self, request: DraftBrief) -> SpecDraft:
        if isinstance(self.draft_or_error, Exception):
            raise self.draft_or_error
        return self.draft_or_error
