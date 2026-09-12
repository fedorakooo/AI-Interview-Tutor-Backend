from __future__ import annotations

import os
from functools import lru_cache


@lru_cache
def feature_enabled(name: str, default: bool = False) -> bool:
    """Read FEATURE_<NAME> env vars (true/1/yes)."""
    raw = os.getenv(f"FEATURE_{name.upper()}", str(default)).strip().lower()
    return raw in {"1", "true", "yes", "on"}


FEATURE_DEFAULTS = {
    "VOICE_INTERVIEW": False,
    "CODING_SANDBOX": True,
    "JD_MATCH": True,
    "STRIPE_BILLING": False,
    "SYSTEM_DESIGN_WHITEBOARD": False,
    "TEAM_ORGS": False,
}
