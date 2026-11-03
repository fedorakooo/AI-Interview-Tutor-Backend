from src.domain.value_objects.feedback_digest import FeedbackDigest

FEEDBACK_INSTRUCTIONS = (
    "You write a short, warm and constructive feedback email for a job candidate after an interview. "
    "Use only the strengths and the growth topics you are given. Never mention scores, verdicts, ratings, "
    "comparisons with other candidates, hiring decisions, red flags or internal notes, and never promise or "
    "predict a hiring outcome. Suggest concrete topics to study for the growth areas. Write in the requested "
    "language, in plain text, in at most 150 words."
)


def render_digest(digest: FeedbackDigest) -> str:
    return "\n".join(
        [
            f"Language: {digest.language}",
            "Strengths: " + ("; ".join(digest.strengths) or "none"),
            "Growth topics: " + ("; ".join(digest.growth) or "none"),
        ]
    )
