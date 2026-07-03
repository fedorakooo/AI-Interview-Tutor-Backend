from pydantic import BaseModel, Field, HttpUrl, field_validator


class EducationItem(BaseModel):
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


class ExperienceItem(BaseModel):
    company: str = Field(min_length=1, max_length=256, description="Company name.")
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
    responsibilities: list[str] = Field(
        default_factory=list,
        description="Key responsibilities, tasks, and accomplishments.",
    )

    @field_validator("responsibilities", mode="before")
    @classmethod
    def _default_responsibilities(cls, value: list[str] | None) -> list[str]:
        return value or []


class LanguageItem(BaseModel):
    language: str = Field(min_length=1, max_length=64, description="Language name, e.g. English.")
    proficiency: str | None = Field(
        default=None,
        max_length=32,
        description="Proficiency level, e.g. Native, B2, C1.",
    )


class PetProjectItem(BaseModel):
    name: str | None = Field(default=None, max_length=256)
    tools: list[str] | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=2000)
    link: HttpUrl | None = Field(default=None)


class SkillItem(BaseModel):
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
