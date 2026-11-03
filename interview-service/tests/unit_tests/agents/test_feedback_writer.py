from pydantic_ai.models.test import TestModel
from src.agents.feedback_writer.agent import FeedbackWriter
from src.agents.feedback_writer.prompts import render_digest
from src.domain.enums.cv_policy import CvPolicy
from src.domain.services.feedback_digest_builder import FeedbackDigestBuilder
from src.domain.services.feedback_leak_detector import FeedbackLeakDetector
from src.domain.value_objects.feedback_digest import FeedbackDigest

from tests.fakes.builders import build_assessment, build_template

TEMPLATE = build_template(CvPolicy.REQUIRED)


def test_rendered_digest_contains_no_internal_details() -> None:
    digest = FeedbackDigestBuilder.build(build_assessment(CvPolicy.REQUIRED), TEMPLATE)

    assert not FeedbackLeakDetector.find(render_digest(digest), TEMPLATE, [])


async def test_feedback_writer_agent_returns_text_without_a_network() -> None:
    writer = FeedbackWriter([], model=TestModel(custom_output_text="  Nice work!  "))

    assert await writer.write(FeedbackDigest("en", ("Python",), ("SQL",))) == "Nice work!"
