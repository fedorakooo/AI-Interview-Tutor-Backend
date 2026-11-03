from dataclasses import dataclass

from src.domain.enums.cv_policy import CvPolicy


@dataclass(frozen=True)
class DraftBrief:
    brief: str
    job_description: str | None = None
    title: str | None = None
    seniority: str | None = None
    language: str = "en"
    cv_policy: CvPolicy = CvPolicy.REQUIRED
    candidate_feedback: bool = False
