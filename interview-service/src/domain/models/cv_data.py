from pydantic import BaseModel, Field, HttpUrl

from src.domain.value_objects.hard_skill import HardSkill
from src.domain.value_objects.language_proficiency import LanguageProficiency


class EducationItem(BaseModel):
    institution: str | None = Field(
        default=None, description="The name of the educational institution, e.g., 'University of Warsaw'."
    )
    faculty: str | None = Field(
        default=None,
        description="The specific faculty or department, e.g., 'Faculty of Mathematics, Informatics, and Mechanics'.",
    )
    degree: str | None = Field(
        default=None, description="The degree obtained or being pursued, e.g., 'Master of Science in Computer Science'."
    )
    start_year: int | None = Field(default=None, description="The year the education started.")
    end_year: int | None = Field(
        default=None, description="The year the education was completed or is expected to be completed."
    )


class ExperienceItem(BaseModel):
    """Represents a single work experience entry in a CV."""

    company: str = Field(description="The name of the company where the user worked.")
    role: str | None = Field(
        default=None, description="The job title or role held at the company, e.g., 'Senior Python Developer'."
    )
    start_date: str | None = Field(
        default=None, description="The start date of the employment, preferably in 'YYYY-MM' format."
    )
    end_date: str | None = Field(
        default=None, description="The end date of the employment. Should be 'Present' if current."
    )
    responsibilities: list[str] = Field(
        description="A list of key responsibilities, tasks, and accomplishments in the role."
    )


class LanguageItem(BaseModel):
    language: str = Field(description="The name of the language, e.g., 'English'.")
    proficiency: LanguageProficiency | None = Field(
        default=None, description="The proficiency level, e.g., 'Native', 'C1'."
    )


class PetProjectItem(BaseModel):
    name: str | None = Field(default=None, description="The name of the personal project.")
    tools: list[str] | None = Field(
        default=None, description="A list of technologies, libraries, or tools used in the project."
    )
    description: str | None = Field(
        default=None, description="A brief description of the project's purpose and functionality."
    )
    link: HttpUrl | None = Field(default=None, description="A URL to the project's repository.")


class CVData(BaseModel):
    user_name: str = Field(description="The full name of the candidate.")
    specialization: str | None = Field(
        default=None, description="The primary professional specialization or desired job title."
    )
    pet_projects: list[PetProjectItem] | None = Field(
        default=None, description="A list of the candidate's personal projects."
    )
    education: list[EducationItem] | None = Field(
        default=None, description="A list detailing the candidate's educational background."
    )
    experience: list[ExperienceItem] | None = Field(
        default=None, description="A list of the candidate's professional work experiences."
    )
    additional_competitive_non_work_achievements: list[str] | None = Field(
        default=None,
        description=(
            "A list of notable achievements outside of standard work, " "such as hackathon wins or competition awards."
        ),
    )
    skills: list[HardSkill] | None = Field(default=None, description="A comprehensive list of the candidate's skills.")
    languages: list[LanguageItem] | None = Field(
        default=None, description="A list of languages the candidate speaks and their proficiency levels."
    )
