"""LLM model routing: cheap models for practice, stronger for final interview reports."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelRoute:
    purpose: str
    model: str
    temperature: float


def route_for(purpose: str) -> ModelRoute:
    purpose = purpose.lower()
    if purpose in {"practice_grade", "flashcard", "mcq"}:
        return ModelRoute(
            purpose=purpose,
            model=os.getenv("LLM_MODEL_CHEAP", os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini")),
            temperature=float(os.getenv("LLM_TEMP_GRADE", "0.2")),
        )
    if purpose in {"interview_report", "final_report"}:
        return ModelRoute(
            purpose=purpose,
            model=os.getenv("LLM_MODEL_STRONG", os.getenv("OPENAI_LLM_MODEL", "gpt-4o")),
            temperature=float(os.getenv("LLM_TEMP_REPORT", "0.4")),
        )
    return ModelRoute(
        purpose=purpose,
        model=os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini"),
        temperature=float(os.getenv("LLM_TEMP_DEFAULT", "0.6")),
    )
