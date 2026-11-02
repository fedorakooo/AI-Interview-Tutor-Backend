from dataclasses import dataclass

from shared_models.assessment import Assessment, AssessmentTemplateSnapshot, Verdict

POSITIVE_VERDICTS = (Verdict.STRONG, Verdict.ADEQUATE)
INTERNAL_MARKERS = ("red flag", "verdict", "not_assessed", "reviewer", "recruiter note")

GREETINGS = {
    "ru": (
        "Спасибо, что прошли интервью.",
        "Что получилось хорошо: {strengths}.",
        "Что стоит подтянуть: {growth}.",
        "Желаем успехов!",
    ),
    "en": (
        "Thank you for taking the interview.",
        "What went well: {strengths}.",
        "What is worth preparing further: {growth}.",
        "We wish you the best of luck!",
    ),
}


@dataclass(frozen=True)
class FeedbackDigest:
    language: str
    strengths: list[str]
    growth: list[str]


def build_digest(assessment: Assessment, template: AssessmentTemplateSnapshot) -> FeedbackDigest:
    """Reduce the report to skill names only, so no verdict or judgement reaches the candidate text."""
    strengths: list[str] = []
    growth: list[str] = []
    for item in assessment.focus:
        focus = template.focus_by_id(item.focus_id)
        if item.final_verdict in POSITIVE_VERDICTS:
            strengths.append(focus.skill)
        else:
            topics = ", ".join(item.missed_must_cover[:3])
            growth.append(f"{focus.skill} ({topics})" if topics else focus.skill)
    return FeedbackDigest(language=template.language, strengths=strengths, growth=growth)


def fallback_text(digest: FeedbackDigest) -> str:
    greeting, strengths_line, growth_line, closing = GREETINGS.get(digest.language[:2], GREETINGS["en"])
    lines = [greeting]
    if digest.strengths:
        lines.append(strengths_line.format(strengths=", ".join(digest.strengths)))
    if digest.growth:
        lines.append(growth_line.format(growth=", ".join(digest.growth)))
    lines.append(closing)
    return "\n".join(lines)


def find_leaks(text: str, template: AssessmentTemplateSnapshot, review_comments: list[str]) -> list[str]:
    """Return the internal details that must never appear in a candidate text."""
    lowered = text.casefold()
    leaks = [flag for flag in template.red_flags if flag.casefold() in lowered]
    leaks += [comment for comment in review_comments if comment.strip() and comment.strip().casefold() in lowered]
    leaks += [marker for marker in INTERNAL_MARKERS if marker in lowered]
    return leaks
