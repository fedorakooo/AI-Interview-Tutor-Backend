from typing import Annotated

from fastapi import APIRouter, Depends
from jwt_handler.value_objects import AccessTokenPayload
from shared_models.question_bank.models import CodingRunRequest, CodingRunResult, LearningPath, QuestionBankItem

from src.api.security import require_authenticated
from src.services.coding.sandbox import run_code

router = APIRouter(prefix="/interview", tags=["Coding & Curriculum"])

QUESTION_BANK: list[QuestionBankItem] = [
    QuestionBankItem(
        question_id="q_two_sum",
        title="Two Sum",
        prompt="Given an array of integers nums and an integer target, return indices of the two numbers that add up to target.",
        category="algorithms",
        difficulty="junior",
        skills=["arrays", "hashmap"],
        company_tags=["faang"],
        interview_mode="coding",
    ),
    QuestionBankItem(
        question_id="q_rate_limiter",
        title="Design a Rate Limiter",
        prompt="Design a distributed rate limiter for an API gateway. Discuss algorithms, storage, and failure modes.",
        category="system_design",
        difficulty="senior",
        skills=["system_design", "redis", "distributed_systems"],
        company_tags=["faang", "startup"],
        interview_mode="system_design",
    ),
    QuestionBankItem(
        question_id="q_conflict",
        title="Tell me about a conflict at work",
        prompt="Describe a time you disagreed with a teammate. What did you do and what was the outcome?",
        category="behavioral",
        difficulty="mid",
        skills=["communication", "star"],
        company_tags=["amazon"],
        interview_mode="behavioral",
    ),
]

LEARNING_PATHS: list[LearningPath] = [
    LearningPath(
        path_id="path_2w_backend",
        title="2-Week Backend Interview Prep",
        duration_days=14,
        focus_skills=["python", "sql", "system_design", "behavioral"],
        milestones=["CV upload", "1 mixed mock", "daily practice", "system design mock", "final mock"],
    ),
    LearningPath(
        path_id="path_30d_faang",
        title="30-Day FAANG Track",
        duration_days=30,
        focus_skills=["algorithms", "system_design", "behavioral", "coding"],
        milestones=["fundamentals", "coding drills", "mocks weekly", "company presets", "final calibration"],
    ),
]


@router.post("/coding/run", response_model=CodingRunResult)
async def coding_run(
    body: CodingRunRequest,
    _: Annotated[AccessTokenPayload, Depends(require_authenticated)],
) -> CodingRunResult:
    return await run_code(body)


@router.get("/question-bank", response_model=list[QuestionBankItem])
async def list_question_bank(
    _: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    category: str | None = None,
) -> list[QuestionBankItem]:
    if category:
        return [item for item in QUESTION_BANK if item.category == category]
    return QUESTION_BANK


@router.get("/learning-paths", response_model=list[LearningPath])
async def list_learning_paths(
    _: Annotated[AccessTokenPayload, Depends(require_authenticated)],
) -> list[LearningPath]:
    return LEARNING_PATHS
