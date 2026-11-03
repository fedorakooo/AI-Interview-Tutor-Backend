from dataclasses import dataclass

from src.domain.enums.coverage_status import CoverageStatus


@dataclass(frozen=True)
class FocusCoverage:
    focus_id: str
    status: CoverageStatus = CoverageStatus.NOT_STARTED
    evidence_count: int = 0
    covered_must_cover: tuple[str, ...] = ()
