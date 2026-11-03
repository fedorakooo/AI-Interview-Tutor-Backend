from datetime import UTC, datetime
from uuid import uuid4

import pytest
from shared_models.assessment import ReviewRequest
from shared_models.assessment.evidence import Verdict as ContractVerdict
from src.application.services.report_loader import GENERATOR_VERSION
from src.domain.enums.cv_policy import CvPolicy
from src.domain.exceptions.report_errors import FocusNotFoundError, ReportNotReadyError
from src.domain.value_objects.assessment_texts import AssessmentTexts

from tests.fakes.ai import ScriptedTextWriter
from tests.fakes.builders import build_context, build_events, build_template, build_texts
from tests.fakes.stack import FakeStack

POLICY = CvPolicy.REQUIRED
TEMPLATE = build_template(POLICY)
ATTEMPT_ID = build_context(POLICY).attempt_id
NOW = datetime(2026, 11, 3, tzinfo=UTC)


def texts(**overrides) -> AssessmentTexts:
    return build_texts(TEMPLATE, **overrides)


class Harness:
    def __init__(
        self, writer_texts: AssessmentTexts | None = None, complete: bool = True, context_error: Exception | None = None
    ) -> None:
        self.stack = FakeStack(
            context=build_context(POLICY),
            context_error=context_error,
            now=NOW,
            text_writer=ScriptedTextWriter(writer_texts),
        )
        self.container = self.stack.container
        self.service = self.container.assessment_report_service
        self.journal = self.stack.event_repository
        self.store = self.stack.assessment_repository
        self.writer = self.stack.text_writer
        session_id = str(ATTEMPT_ID)
        source = build_events(POLICY) if complete else build_events(POLICY)[:-2]
        self.journal.events[session_id] = [self._rebind(event, session_id) for event in source]

    @staticmethod
    def _rebind(event, session_id: str):
        from dataclasses import replace

        return replace(event, session_id=session_id)


async def test_report_is_generated_once_and_cached() -> None:
    harness = Harness(texts())

    first = await harness.service.get_overview(ATTEMPT_ID)
    second = await harness.service.get_overview(ATTEMPT_ID)

    assert first == second
    assert len(harness.writer.digests) == 1
    assert first.generator_version == GENERATOR_VERSION
    assert {item.focus_id: item.verdict for item in first.focus}["async_io"] == ContractVerdict.WEAK


async def test_writer_failure_still_produces_a_report() -> None:
    harness = Harness()

    overview = await harness.service.get_overview(ATTEMPT_ID)

    assert overview.red_flags == []
    assert len(overview.focus) == len(TEMPLATE.criteria)


async def test_report_is_not_available_before_the_interview_ends() -> None:
    for complete in (True, False):
        harness = Harness(texts(), complete=complete)
        if complete:
            harness.journal.events.clear()
        with pytest.raises(ReportNotReadyError):
            await harness.service.get_overview(ATTEMPT_ID)


async def test_focus_detail_exposes_the_timeline_with_quotes() -> None:
    detail = await Harness(texts()).service.get_focus_detail(ATTEMPT_ID, "databases")

    assert detail.reference_answer
    assert detail.timeline[0].evidence and detail.timeline[0].evidence.quotes
    with pytest.raises(FocusNotFoundError):
        await Harness(texts()).service.get_focus_detail(ATTEMPT_ID, "unknown")


async def test_reviews_are_appended_and_override_the_final_verdict() -> None:
    harness = Harness(texts())
    reviewer = uuid4()

    await harness.service.add_review(
        ATTEMPT_ID, "async_io", ReviewRequest(author_id=reviewer, comment="Asked again, fine")
    )
    detail = await harness.service.add_review(
        ATTEMPT_ID,
        "async_io",
        ReviewRequest(author_id=reviewer, comment="Overall adequate", manual_verdict=ContractVerdict.ADEQUATE),
    )
    overview = await harness.service.get_overview(ATTEMPT_ID)

    assert [entry.comment for entry in detail.focus.review] == ["Asked again, fine", "Overall adequate"]
    assert detail.focus.verdict == ContractVerdict.WEAK and detail.focus.final_verdict == ContractVerdict.ADEQUATE
    row = next(item for item in overview.focus if item.focus_id == "async_io")
    assert (row.verdict, row.final_verdict, row.reviewed) == (ContractVerdict.WEAK, ContractVerdict.ADEQUATE, True)
    assert len(harness.store.reviews) == 2
