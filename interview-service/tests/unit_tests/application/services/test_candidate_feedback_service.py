from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from shared_models.assessment import ReviewRequest
from shared_models.assessment.evidence import Verdict as ContractVerdict
from src.domain.enums.cv_policy import CvPolicy
from src.domain.exceptions.feedback_errors import FeedbackDisabledError, FeedbackLeakError
from src.domain.exceptions.report_errors import ReportNotReadyError
from src.domain.services.feedback_leak_detector import FeedbackLeakDetector

from tests.fakes.ai import ScriptedFeedbackWriter, ScriptedTextWriter
from tests.fakes.builders import build_context, build_template, build_texts
from tests.fakes.stack import completed_stack

POLICY = CvPolicy.REQUIRED
TEMPLATE = build_template(POLICY)
ATTEMPT_ID = build_context(POLICY).attempt_id
NOW = datetime(2026, 11, 3, tzinfo=UTC)
FLAG = TEMPLATE.red_flags[1]


def harness_for(writer=None, template=TEMPLATE):
    context = replace(build_context(POLICY), template=template)
    stack = completed_stack(
        context=context,
        now=NOW,
        text_writer=ScriptedTextWriter(build_texts(TEMPLATE)),
        feedback_writer=writer or ScriptedFeedbackWriter(),
    )
    return stack, template


async def test_feedback_is_generated_once_and_cached() -> None:
    stack, _ = harness_for()
    service = stack.container.candidate_feedback_service

    first = await service.get(ATTEMPT_ID)
    second = await service.get(ATTEMPT_ID)

    assert first == second and first.version == 1 and first.source == "generated"
    assert len(stack.feedback_writer.digests) == 1 and len(stack.feedback_repository.versions) == 1


@pytest.mark.parametrize(
    "writer",
    [
        ScriptedFeedbackWriter(None),
        ScriptedFeedbackWriter(f"We noticed a red flag: {FLAG}"),
        ScriptedFeedbackWriter("Your verdict was weak."),
    ],
)
async def test_unsafe_or_failed_generation_falls_back_to_the_deterministic_text(writer) -> None:
    stack, template = harness_for(writer)

    feedback = await stack.container.candidate_feedback_service.get(ATTEMPT_ID)

    assert "Python fundamentals" in feedback.text and not FeedbackLeakDetector.find(feedback.text, template, [])


async def test_feedback_requires_the_template_to_allow_it_and_a_finished_interview() -> None:
    stack, template = harness_for()
    disabled = replace(template, candidate_feedback=False)

    with pytest.raises(FeedbackDisabledError):
        await harness_for(template=disabled)[0].container.candidate_feedback_service.get(ATTEMPT_ID)
    stack.event_repository.events.clear()
    with pytest.raises(ReportNotReadyError):
        await stack.container.candidate_feedback_service.get(ATTEMPT_ID)


async def test_edit_creates_a_new_version_and_rejects_internal_details() -> None:
    stack, _ = harness_for()
    editor = uuid4()
    await stack.container.assessment_report_service.add_review(
        ATTEMPT_ID,
        "async_io",
        ReviewRequest(author_id=editor, comment="Weak on loops", manual_verdict=ContractVerdict.WEAK),
    )
    service = stack.container.candidate_feedback_service

    edited = await service.edit(ATTEMPT_ID, editor, "  Thanks, great talk!  ")

    assert (edited.version, edited.source, edited.editor_id, edited.text) == (
        2,
        "edited",
        editor,
        "Thanks, great talk!",
    )
    assert (await stack.feedback_repository.latest(ATTEMPT_ID)).version == 2
    for text in (f"Concern: {FLAG}", "As the reviewer wrote: weak on loops"):
        with pytest.raises(FeedbackLeakError):
            await service.edit(ATTEMPT_ID, editor, text)
    assert (await stack.feedback_repository.latest(ATTEMPT_ID)).version == 2
