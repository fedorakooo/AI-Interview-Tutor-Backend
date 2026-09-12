from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from jwt_handler.value_objects import AccessTokenPayload
from shared_models.cv.cv_items import ExperienceItem, SkillItem
from shared_models.jd.match import JDMatchRequest, JDMatchResult, JDRequirement

from src.api.dependencies.mongo import get_cv_analysis_repository
from src.api.security import require_authenticated
from src.domain.interfaces.mongo import IMongoRepository
from src.services.cv_data_resolver import CVDataResolver

router = APIRouter(prefix="/analyze", tags=["JD Match"])

SKILL_HINTS = [
    "python",
    "java",
    "javascript",
    "typescript",
    "react",
    "node",
    "sql",
    "postgres",
    "mongodb",
    "redis",
    "kafka",
    "aws",
    "gcp",
    "docker",
    "kubernetes",
    "fastapi",
    "django",
    "flask",
    "system design",
    "microservices",
    "ci/cd",
    "graphql",
    "rest",
    "llm",
    "machine learning",
]


def _extract_skills(text: str) -> set[str]:
    lowered = text.lower()
    found = {skill for skill in SKILL_HINTS if skill in lowered}
    # Also capture CapitalCase / snake tokens that look like tech
    for token in re.findall(r"[A-Za-z][A-Za-z0-9+.#-]{2,}", text):
        if token.lower() in SKILL_HINTS:
            found.add(token.lower())
    return found


@router.post("/jd-match", response_model=JDMatchResult)
async def jd_match(
    body: JDMatchRequest,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    mongo_repository: Annotated[IMongoRepository, Depends(get_cv_analysis_repository)],
) -> JDMatchResult:
    resolver = CVDataResolver(mongo_repository=mongo_repository)
    try:
        resolution = await resolver.resolve(payload["id"])
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    cv = resolution.cv_data
    cv_skills: set[str] = set()
    for skill in getattr(cv, "skills", None) or []:
        if isinstance(skill, SkillItem):
            cv_skills.add(skill.name.lower())
        else:
            name = getattr(skill, "name", None) or str(skill)
            cv_skills.add(str(name).lower())
    for exp in getattr(cv, "experience", None) or []:
        if isinstance(exp, ExperienceItem):
            blob = " ".join(exp.responsibilities)
            blob = f"{blob} {exp.role or ''}"
        else:
            blob = " ".join(getattr(exp, "responsibilities", None) or [])
            blob = f"{blob} {getattr(exp, 'role', '') or ''}"
        for token in blob.lower().split():
            cleaned = token.strip(".,;:()[]")
            if cleaned in SKILL_HINTS:
                cv_skills.add(cleaned)
    for project in getattr(cv, "pet_projects", None) or []:
        for tool in getattr(project, "tools", None) or []:
            cv_skills.add(str(tool).lower())

    required = _extract_skills(body.job_description)
    if not required:
        required = {"communication", "problem solving"}

    matched = sorted(required & cv_skills) if cv_skills else []
    # Fuzzy: substring contains
    if not matched and cv_skills:
        for req in required:
            for skill in cv_skills:
                if req in skill or skill in req:
                    matched.append(req)
                    break
        matched = sorted(set(matched))

    missing = sorted(required - set(matched))
    score = round(100.0 * (len(matched) / max(len(required), 1)), 1)
    requirements = [
        JDRequirement(skill=skill, importance="required", evidence="mentioned in JD") for skill in sorted(required)
    ]
    recommendations = [
        f"Practice drills for: {', '.join(missing[:5])}" if missing else "Strong overlap — run a role-targeted mock.",
        "Generate a practice plan focused on missing skills.",
        "Start a technical interview with this JD attached for personalization.",
    ]
    summary = (
        f"Match score {score}%. Covered {len(matched)}/{len(required)} detected JD skills. "
        f"Missing: {', '.join(missing[:8]) or 'none'}."
    )
    return JDMatchResult(
        match_score=score,
        matched_skills=matched,
        missing_skills=missing,
        recommendations=recommendations,
        requirements=requirements,
        summary=summary,
    )
