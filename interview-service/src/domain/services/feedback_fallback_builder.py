from src.domain.value_objects.feedback_digest import FeedbackDigest

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


class FeedbackFallbackBuilder:
    @staticmethod
    def build(digest: FeedbackDigest) -> str:
        greeting, strengths_line, growth_line, closing = GREETINGS.get(digest.language[:2], GREETINGS["en"])
        lines = [greeting]
        if digest.strengths:
            lines.append(strengths_line.format(strengths=", ".join(digest.strengths)))
        if digest.growth:
            lines.append(growth_line.format(growth=", ".join(digest.growth)))
        lines.append(closing)
        return "\n".join(lines)
