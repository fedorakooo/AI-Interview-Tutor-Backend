from dataclasses import dataclass

from src.domain.value_objects.cv_experience import CvExperience


@dataclass(frozen=True)
class CandidateCv:
    specialization: str | None = None
    skills: tuple[str, ...] = ()
    experience: tuple[CvExperience, ...] = ()
