from dataclasses import dataclass


@dataclass(frozen=True)
class FeedbackDigest:
    language: str
    strengths: tuple[str, ...]
    growth: tuple[str, ...]
