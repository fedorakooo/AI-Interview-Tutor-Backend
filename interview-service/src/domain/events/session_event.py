from src.domain.events.candidate_message import CandidateMessage
from src.domain.events.evidence_recorded import EvidenceRecorded
from src.domain.events.focus_coverage_changed import FocusCoverageChanged
from src.domain.events.interviewer_message import InterviewerMessage
from src.domain.events.session_completed import SessionCompleted
from src.domain.events.session_failed import SessionFailed
from src.domain.events.session_paused import SessionPaused
from src.domain.events.session_started import SessionStarted

SessionEvent = (
    SessionStarted
    | InterviewerMessage
    | CandidateMessage
    | EvidenceRecorded
    | FocusCoverageChanged
    | SessionPaused
    | SessionCompleted
    | SessionFailed
)
