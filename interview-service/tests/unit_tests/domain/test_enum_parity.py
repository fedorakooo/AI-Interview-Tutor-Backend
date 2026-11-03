import pytest
from shared_models.assessment import contracts, evidence, session_events, session_state

from src.domain.enums.assessment_mode import AssessmentMode
from src.domain.enums.completion_reason import CompletionReason
from src.domain.enums.coverage_status import CoverageStatus
from src.domain.enums.cv_policy import CvPolicy
from src.domain.enums.evidence_level import EvidenceLevel
from src.domain.enums.focus_method import FocusMethod
from src.domain.enums.message_kind import MessageKind
from src.domain.enums.pause_reason import PauseReason
from src.domain.enums.session_status import SessionStatus
from src.domain.enums.verdict import Verdict

PAIRS = [
    (Verdict, evidence.Verdict),
    (EvidenceLevel, evidence.EvidenceLevel),
    (CvPolicy, contracts.CvPolicy),
    (AssessmentMode, contracts.AssessmentMode),
    (FocusMethod, contracts.FocusMethod),
    (MessageKind, session_events.MessageKind),
    (CoverageStatus, session_events.CoverageStatus),
    (CompletionReason, session_events.CompletionReason),
    (PauseReason, session_events.PauseReason),
    (SessionStatus, session_state.SessionStatus),
]


@pytest.mark.parametrize(("domain_enum", "contract_enum"), PAIRS, ids=[pair[0].__name__ for pair in PAIRS])
def test_domain_enum_matches_contract_values(domain_enum, contract_enum) -> None:
    assert {member.name: member.value for member in domain_enum} == {
        member.name: member.value for member in contract_enum
    }
