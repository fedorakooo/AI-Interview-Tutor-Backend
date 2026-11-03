from dataclasses import dataclass

from src.domain.enums.coverage_status import CoverageStatus
from src.domain.events.session_event_base import SessionEventBase


@dataclass(frozen=True, kw_only=True)
class FocusCoverageChanged(SessionEventBase):
    focus_id: str
    status: CoverageStatus
    evidence_count: int
    covered_must_cover: tuple[str, ...] = ()
