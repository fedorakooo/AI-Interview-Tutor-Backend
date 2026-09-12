#!/usr/bin/env python3
"""Export OpenAPI schemas from importable FastAPI apps."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "openapi"
OUT.mkdir(parents=True, exist_ok=True)

COMMON_PATHS = [
    ROOT / "libs" / "jwt_handler",
    ROOT / "libs" / "shared_models",
    ROOT / "libs" / "observability",
]


def _try_import_app(service_dir: Path, module: str, label: str):
    paths = [str(service_dir), *[str(p) for p in COMMON_PATHS]]
    sys.path[:0] = [p for p in paths if p not in sys.path]
    os.chdir(service_dir)
    try:
        mod = __import__(module, fromlist=["app"])
        return label, mod.app
    except Exception as exc:
        print(f"skip {label}: {exc}")
        return None
    finally:
        for p in paths:
            if p in sys.path:
                sys.path.remove(p)


def main() -> None:
    targets = [
        (ROOT / "user-management-service", "src.main", "user-management"),
        (ROOT / "interview-service", "src.main", "interview"),
        (ROOT / "practice-service", "src.main", "practice"),
    ]
    for service_dir, module, label in targets:
        result = _try_import_app(service_dir, module, label)
        if result is None:
            continue
        name, app = result
        schema = app.openapi()
        path = OUT / f"{name}.openapi.json"
        path.write_text(json.dumps(schema, indent=2))
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
