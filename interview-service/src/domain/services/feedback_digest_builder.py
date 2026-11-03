from src.domain.entities.assessment import Assessment
from src.domain.enums.verdict import Verdict
from src.domain.value_objects.feedback_digest import FeedbackDigest
from src.domain.value_objects.interview_template import InterviewTemplate

POSITIVE_VERDICTS = (Verdict.STRONG, Verdict.ADEQUATE)


class FeedbackDigestBuilder:
    @staticmethod
    def build(assessment: Assessment, template: InterviewTemplate) -> FeedbackDigest:
        strengths: list[str] = []
        growth: list[str] = []
        for item in assessment.focus:
            focus = template.focus_by_id(item.focus_id)
            if item.final_verdict in POSITIVE_VERDICTS:
                strengths.append(focus.skill)
            else:
                topics = ", ".join(item.missed_must_cover[:3])
                growth.append(f"{focus.skill} ({topics})" if topics else focus.skill)
        return FeedbackDigest(language=template.language, strengths=tuple(strengths), growth=tuple(growth))
