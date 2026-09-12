from __future__ import annotations

PRESETS: dict[str, dict[str, str]] = {
    "amazon_lp": {
        "label": "Amazon Leadership Principles",
        "guidance": (
            "Probe Leadership Principles (Customer Obsession, Ownership, Dive Deep, Bias for Action). "
            "Prefer STAR answers with metrics."
        ),
    },
    "google_behavioral": {
        "label": "Google behavioral",
        "guidance": (
            "Focus on Googleyness, cognitive ability storytelling, collaboration, and role-related knowledge. "
            "Keep follow-ups concrete."
        ),
    },
    "faang_system_design": {
        "label": "FAANG system design",
        "guidance": (
            "Drive requirements, capacity, API design, data model, bottlenecks, and trade-offs. "
            "Push for numbers and failure modes."
        ),
    },
    "startup": {
        "label": "Startup generalist",
        "guidance": (
            "Emphasize ownership, shipping speed, ambiguity tolerance, and wearing multiple hats. "
            "Technical depth should still be real."
        ),
    },
    "backend": {
        "label": "Backend track",
        "guidance": "Focus on APIs, databases, concurrency, reliability, and observability.",
    },
    "frontend": {
        "label": "Frontend track",
        "guidance": "Focus on UI architecture, performance, accessibility, state management, and browser APIs.",
    },
    "ml": {
        "label": "ML track",
        "guidance": "Focus on modeling choices, data quality, evaluation metrics, MLOps, and production constraints.",
    },
}


def preset_guidance(preset_key: str | None) -> str:
    if not preset_key:
        return ""
    preset = PRESETS.get(preset_key)
    if not preset:
        return ""
    return f"Company/role preset ({preset['label']}): {preset['guidance']}"
