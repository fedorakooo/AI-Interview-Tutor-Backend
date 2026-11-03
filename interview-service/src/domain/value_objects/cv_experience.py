from dataclasses import dataclass


@dataclass(frozen=True)
class CvExperience:
    role: str | None = None
    company: str | None = None
    technologies: tuple[str, ...] = ()
