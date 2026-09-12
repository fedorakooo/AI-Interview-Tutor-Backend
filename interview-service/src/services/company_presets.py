from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PRESETS_PATH = Path(__file__).resolve().parent.parent / "data" / "company_presets.yaml"


@lru_cache(maxsize=1)
def load_company_presets() -> dict[str, dict[str, Any]]:
    if not PRESETS_PATH.exists():
        return {}
    with PRESETS_PATH.open() as handle:
        data = yaml.safe_load(handle) or {}
    return {str(key): value for key, value in data.items()}


def preset_context(preset_key: str | None) -> str:
    if not preset_key:
        return ""
    preset = load_company_presets().get(preset_key)
    if not preset:
        return ""
    hints = preset.get("question_hints") or []
    hints_text = "\n".join(f"- {hint}" for hint in hints)
    return (
        f"Company preset: {preset.get('name', preset_key)}\n"
        f"Focus: {preset.get('focus', '')}\n"
        f"Guidance:\n{hints_text}"
    )
