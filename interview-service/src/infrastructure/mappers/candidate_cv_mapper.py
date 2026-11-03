from shared_models.cv.cv_data import CVData

from src.domain.value_objects.candidate_cv import CandidateCv
from src.domain.value_objects.cv_experience import CvExperience


class CandidateCvMapper:
    @staticmethod
    def to_domain(cv: CVData) -> CandidateCv:
        return CandidateCv(
            specialization=cv.specialization,
            skills=tuple(skill.name for skill in cv.skills or []),
            experience=tuple(
                CvExperience(role=item.role, company=item.company, technologies=tuple(item.technologies))
                for item in cv.experience or []
            ),
        )
