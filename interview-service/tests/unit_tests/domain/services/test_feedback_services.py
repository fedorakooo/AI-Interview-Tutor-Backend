import pytest
from src.domain.enums.cv_policy import CvPolicy
from src.domain.services.feedback_digest_builder import FeedbackDigestBuilder
from src.domain.services.feedback_fallback_builder import FeedbackFallbackBuilder
from src.domain.services.feedback_leak_detector import FeedbackLeakDetector
from src.domain.value_objects.feedback_digest import FeedbackDigest

from tests.fakes.builders import build_assessment, build_template

POLICY = CvPolicy.REQUIRED
TEMPLATE = build_template(POLICY)
FLAG = TEMPLATE.red_flags[1]


def test_digest_contains_only_skill_names_and_missed_topics() -> None:
    digest = FeedbackDigestBuilder.build(build_assessment(POLICY), TEMPLATE)

    assert digest.strengths == ("Python fundamentals", "SQL and PostgreSQL", "REST API design with FastAPI")
    assert "Async and concurrency (blocking calls, task cancellation)" in digest.growth
    assert "Testing and code quality (unit vs integration tests)" in digest.growth


@pytest.mark.parametrize("language", ["en", "ru", "de"])
def test_fallback_text_is_safe_in_every_language(language: str) -> None:
    digest = FeedbackDigestBuilder.build(build_assessment(POLICY), TEMPLATE)

    text = FeedbackFallbackBuilder.build(FeedbackDigest(language, digest.strengths, digest.growth))

    assert "Python fundamentals" in text and not FeedbackLeakDetector.find(text, TEMPLATE, [])


def test_leak_detection_covers_red_flags_review_comments_and_internal_words() -> None:
    assert FeedbackLeakDetector.find(f"Note: {FLAG.lower()}.", TEMPLATE, [])
    assert FeedbackLeakDetector.find("Great job!", TEMPLATE, ["Needs a second look"]) == []
    assert FeedbackLeakDetector.find("The reviewer said needs a second look", TEMPLATE, ["Needs a second look"])
    assert FeedbackLeakDetector.find("Your verdict is weak", TEMPLATE, [])
    assert FeedbackLeakDetector.find("You showed real confidence with Python.", TEMPLATE, []) == []
