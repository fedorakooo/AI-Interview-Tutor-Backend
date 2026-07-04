from pydantic import BaseModel, ConfigDict, Field, field_validator

from shared_models.cv.cv_items import (
    EducationItem,
    ExperienceItem,
    LanguageItem,
    PetProjectItem,
    SkillItem,
)


class CVData(BaseModel):
    """Structured resume content extracted from a candidate CV."""

    model_config = ConfigDict(str_strip_whitespace=True)

    user_name: str = Field(min_length=1, max_length=256, description="Full name of the candidate.")
    specialization: str | None = Field(
        default=None,
        max_length=256,
        description="Primary professional specialization or desired job title.",
    )
    pet_projects: list[PetProjectItem] | None = Field(
        default=None,
        description="Personal or hobby projects explicitly mentioned in the resume.",
    )
    education: list[EducationItem] | None = Field(default=None, description="Educational background.")
    experience: list[ExperienceItem] | None = Field(default=None, description="Professional work experience.")
    additional_competitive_non_work_achievements: list[str] | None = Field(
        default=None,
        description="Notable non-work achievements such as hackathon wins or competition awards.",
    )
    skills: list[SkillItem] | None = Field(
        default=None,
        description="Technical and professional skills extracted from the resume.",
    )
    languages: list[LanguageItem] | None = Field(default=None, description="Spoken languages and proficiency.")

    @field_validator("skills", mode="before")
    @classmethod
    def _coerce_legacy_skills(
        cls, value: list[SkillItem | str | dict[str, str | None]] | None
    ) -> list[SkillItem] | None:
        if value is None:
            return None

        coerced: list[SkillItem] = []
        for item in value:
            if isinstance(item, SkillItem):
                coerced.append(item)
            elif isinstance(item, str):
                coerced.append(SkillItem(name=item))
            elif isinstance(item, dict):
                coerced.append(SkillItem.model_validate(item))
            else:
                raise TypeError(f"Unsupported skill item type: {type(item)!r}")

        return coerced
