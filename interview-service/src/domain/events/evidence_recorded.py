from dataclasses import dataclass

from src.domain.events.session_event_base import SessionEventBase
from src.domain.value_objects.evidence_item import EvidenceItem


@dataclass(frozen=True, kw_only=True)
class EvidenceRecorded(SessionEventBase):
    evidence: EvidenceItem
