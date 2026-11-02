import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
COMPOSITION_ROOTS = {SRC / "main.py", SRC / "app" / "lifespan.py"}
LEGACY_IMPORT = re.compile(r"^\s*(from|import)\s+src\.legacy\b", re.MULTILINE)


def test_only_composition_roots_import_the_legacy_package() -> None:
    offenders = [
        str(path.relative_to(SRC))
        for path in SRC.rglob("*.py")
        if SRC / "legacy" not in path.parents
        and path not in COMPOSITION_ROOTS
        and LEGACY_IMPORT.search(path.read_text(encoding="utf-8"))
    ]

    assert offenders == []


def test_legacy_package_holds_the_langgraph_code() -> None:
    langgraph_files = {
        path
        for path in SRC.rglob("*.py")
        if re.search(r"^\s*(from|import)\s+(langgraph|langchain)", path.read_text(encoding="utf-8"), re.MULTILINE)
    }

    assert langgraph_files
    assert all(SRC / "legacy" in path.parents for path in langgraph_files)
