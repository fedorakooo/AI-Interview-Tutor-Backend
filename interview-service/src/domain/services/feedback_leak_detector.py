from collections.abc import Sequence

from src.domain.value_objects.interview_template import InterviewTemplate

INTERNAL_MARKERS = ("red flag", "verdict", "not_assessed", "reviewer", "recruiter note")


class FeedbackLeakDetector:
    @staticmethod
    def find(text: str, template: InterviewTemplate, review_comments: Sequence[str]) -> list[str]:
        lowered = text.casefold()
        leaks = [flag for flag in template.red_flags if flag.casefold() in lowered]
        leaks += [comment for comment in review_comments if comment.strip() and comment.strip().casefold() in lowered]
        leaks += [marker for marker in INTERNAL_MARKERS if marker in lowered]
        return leaks
