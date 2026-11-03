import ast
import importlib
import sys
from pathlib import Path

from tests.unit_tests.architecture_allowlist import ALLOWED_VIOLATIONS

SRC = Path(__file__).resolve().parents[2] / "src"
LAYERS = {"domain", "application", "agents", "infrastructure", "api", "app"}
TOP_LEVEL_MODULES = {"config", "logger", "main"}

ALLOWED_LAYER_IMPORTS: dict[str, set[str]] = {
    "domain": {"domain"},
    "application": {"domain", "application"},
    "agents": {"domain", "agents"},
    "infrastructure": {"domain", "infrastructure"},
    "api": {"api", "domain", "application"},
    "app": {"domain", "application", "agents", "infrastructure", "app"},
    "main": LAYERS,
}
ALLOWED_SUBPACKAGES: dict[tuple[str, str], set[str]] = {
    ("api", "domain"): {"exceptions", "entities"},
    ("api", "application"): {"interfaces", "dtos"},
}
ALLOWED_TOP_LEVEL_IMPORTS: dict[str, set[str]] = {
    "api": {"config"},
    "infrastructure": {"config"},
    "app": {"config", "logger"},
    "logger": {"config"},
    "main": TOP_LEVEL_MODULES,
}

DRIVERS = {"motor", "pymongo", "bson", "redis", "aio_pika", "aiormq", "httpx"}
WEB = {"fastapi", "starlette", "uvicorn"}
AI = {"pydantic_ai"}
FORBIDDEN_THIRD_PARTY: dict[str, set[str]] = {
    "application": DRIVERS | WEB | AI,
    "infrastructure": WEB | AI,
    "api": DRIVERS | AI,
}
ALLOWED_THIRD_PARTY: dict[str, set[str]] = {
    "domain": set(),
    "agents": AI | {"pydantic"},
}
SHARED_MODELS_FORBIDDEN = {"domain", "agents"}
SHARED_MODELS_VIEWS_ONLY = {"application"}
SHARED_MODELS_VIEWS_MODULE = "shared_models.assessment.views"


def _layer_of(path: Path) -> str:
    parts = path.relative_to(SRC).parts
    return parts[0] if len(parts) > 1 else path.stem


def _is_src_module(module: str) -> bool:
    candidate = SRC.parent.joinpath(*module.split("."))
    return candidate.is_dir() or candidate.with_suffix(".py").is_file()


def _imported_modules(tree: ast.AST) -> list[str]:
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                modules.append("." * node.level + (node.module or ""))
                continue
            module = node.module or ""
            for alias in node.names:
                nested = f"{module}.{alias.name}"
                if module.startswith("src") and _is_src_module(nested):
                    modules.append(nested)
                elif module.startswith("shared_models"):
                    modules.append(nested)
                else:
                    modules.append(module)
    return modules


def _shared_models_defining_module(target: str) -> str:
    module_name, _, name = target.rpartition(".")
    try:
        module = importlib.import_module(module_name)
    except ImportError:
        return module_name
    return getattr(getattr(module, name, None), "__module__", None) or target


def _check_src_import(layer: str, module: str) -> str | None:
    parts = module.split(".")
    target = parts[1] if len(parts) > 1 else ""
    if target in TOP_LEVEL_MODULES:
        return None if target in ALLOWED_TOP_LEVEL_IMPORTS.get(layer, set()) else "top-level module not allowed"
    if target not in LAYERS:
        return None
    if target not in ALLOWED_LAYER_IMPORTS.get(layer, set()):
        return f"layer {layer} must not import {target}"
    allowed_sub = ALLOWED_SUBPACKAGES.get((layer, target))
    if allowed_sub is not None and (len(parts) < 3 or parts[2] not in allowed_sub):
        return f"layer {layer} may import only {sorted(allowed_sub)} of {target}"
    return None


def _check_shared_models_import(layer: str, module: str) -> str | None:
    if layer in SHARED_MODELS_FORBIDDEN:
        return f"layer {layer} must not import shared_models"
    if layer in SHARED_MODELS_VIEWS_ONLY and _shared_models_defining_module(module) != SHARED_MODELS_VIEWS_MODULE:
        return f"layer {layer} may import only shared_models views and requests"
    return None


def _check_third_party_import(layer: str, module: str) -> str | None:
    root = module.split(".")[0]
    if root in sys.stdlib_module_names:
        return None
    if layer in ALLOWED_THIRD_PARTY and root not in ALLOWED_THIRD_PARTY[layer]:
        return f"layer {layer} must not import third-party {root}"
    if root in FORBIDDEN_THIRD_PARTY.get(layer, set()):
        return f"layer {layer} must not import {root}"
    return None


def _check_import(layer: str, module: str) -> str | None:
    if module.startswith("."):
        return "relative import"
    root = module.split(".")[0]
    if root == "src":
        return _check_src_import(layer, module)
    if root == "shared_models":
        return _check_shared_models_import(layer, module)
    return _check_third_party_import(layer, module)


def collect_violations() -> dict[str, str]:
    violations: dict[str, str] = {}
    for path in sorted(SRC.rglob("*.py")):
        layer = _layer_of(path)
        if layer not in LAYERS and layer not in TOP_LEVEL_MODULES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for module in _imported_modules(tree):
            reason = _check_import(layer, module)
            if reason is not None:
                violations[f"{path.relative_to(SRC).as_posix()} -> {module}"] = reason
    return violations


def test_no_new_import_violations() -> None:
    new = {key: reason for key, reason in collect_violations().items() if key not in ALLOWED_VIOLATIONS}
    assert not new, "Imports break the layer rules in AGENTS.md section 2:\n" + "\n".join(
        f"{key}: {reason}" for key, reason in sorted(new.items())
    )


def test_allowlist_has_no_stale_entries() -> None:
    stale = sorted(ALLOWED_VIOLATIONS - set(collect_violations()))
    assert not stale, "Remove fixed violations from architecture_allowlist.py:\n" + "\n".join(stale)
