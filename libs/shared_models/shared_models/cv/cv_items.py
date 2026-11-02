from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, field_validator

_NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class EducationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    institution: str | None = Field(
        default=None,
        max_length=256,
        description="The name of the educational institution, e.g., 'University of Warsaw'.",
    )
    faculty: str | None = Field(
        default=None,
        max_length=256,
        description="The specific faculty or department.",
    )
    degree: str | None = Field(
        default=None,
        max_length=256,
        description="The degree obtained or being pursued.",
    )
    start_year: int | None = Field(default=None, ge=1900, le=2100)
    end_year: int | None = Field(default=None, ge=1900, le=2100)


class AchievementItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: _NonEmptyText = Field(description="Result explicitly stated in the resume.")
    metric_as_stated: str | None = Field(
        default=None,
        description="Stated metric with its original units and context; do not calculate missing values.",
    )


class ExperienceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: str | None = Field(default=None, min_length=1, max_length=256, description="Company name, if stated.")
    role: str | None = Field(default=None, max_length=256, description="Job title or role.")
    start_date: str | None = Field(
        default=None,
        max_length=32,
        description="Employment start date, preferably YYYY-MM.",
    )
    end_date: str | None = Field(
        default=None,
        max_length=32,
        description="Employment end date or 'Present' if current.",
    )
    responsibilities: list[_NonEmptyText] = Field(
        default_factory=list,
        description="Responsibilities and tasks performed in this role, separate from achievements.",
    )
    achievements: list[AchievementItem] = Field(
        default_factory=list,
        description="Results stated for this role; preserve whether they are attributed to the candidate or the team.",
    )
    technologies: list[_NonEmptyText] = Field(
        default_factory=list,
        description="Technologies explicitly linked to this role, not copied from the global skills list.",
    )

    @field_validator("company", mode="before")
    @classmethod
    def _normalize_company(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("responsibilities", "achievements", "technologies", mode="before")
    @classmethod
    def _default_lists(cls, value: Any) -> Any:
        return [] if value is None else value


class LanguageItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: str = Field(min_length=1, max_length=64, description="Language name, e.g. English.")
    proficiency: str | None = Field(
        default=None,
        max_length=32,
        description="Proficiency level, e.g. Native, B2, C1.",
    )


class PetProjectItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=256)
    tools: list[str] | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=2000)
    link: HttpUrl | None = Field(default=None)


class SkillItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        min_length=1,
        max_length=128,
        description="Skill or technology name as it should appear in interview context.",
    )
    category: str | None = Field(
        default=None,
        max_length=64,
        description=(
            "Optional skill grouping, e.g. programming_language, framework, database, "
            "cloud, devops, messaging, methodology."
        ),
    )
