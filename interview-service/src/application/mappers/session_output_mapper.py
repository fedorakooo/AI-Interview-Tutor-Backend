from src.application.dtos.message_completed import MessageCompleted
from src.application.dtos.session_finished import SessionFinished
from src.application.dtos.transcript_entry import TranscriptEntry
from src.domain.events.candidate_message import CandidateMessage
from src.domain.events.interviewer_message import InterviewerMessage
from src.domain.events.session_completed import SessionCompleted
from src.domain.events.session_event import SessionEvent


class SessionOutputMapper:
    @staticmethod
    def message_completed(event: InterviewerMessage) -> MessageCompleted:
        return MessageCompleted(turn_id=event.turn_id, event_id=event.event_id, seq=event.seq, text=event.text)

    @staticmethod
    def session_finished(event: SessionCompleted) -> SessionFinished:
        return SessionFinished(event_id=event.event_id, seq=event.seq)

    @staticmethod
    def transcript_entry(event: SessionEvent) -> TranscriptEntry | SessionFinished | None:
        if isinstance(event, InterviewerMessage | CandidateMessage):
            role = "interviewer" if isinstance(event, InterviewerMessage) else "candidate"
            return TranscriptEntry(
                event_id=event.event_id, seq=event.seq, role=role, text=event.text, occurred_at=event.occurred_at
            )
        if isinstance(event, SessionCompleted):
            return SessionOutputMapper.session_finished(event)
        return None
