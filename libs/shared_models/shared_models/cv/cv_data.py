from typing import Any

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

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    user_name: str | None = Field(
        default=None, min_length=1, max_length=256, description="Full name of the candidate, if stated."
    )
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

    @field_validator("user_name", mode="before")
    @classmethod
    def _normalize_user_name(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip() or None
        return value
