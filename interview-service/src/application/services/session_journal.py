from collections.abc import Sequence

from shared_models.assessment import SessionEvent, SessionState, fold_events
from shared_models.assessment.session_state import InvalidEventLogError

from src.domain.exceptions.session_errors import InconsistentJournalError


def fold_journal(events: Sequence[SessionEvent]) -> SessionState:
    try:
        return fold_events(events)
    except InvalidEventLogError as exc:
        raise InconsistentJournalError() from exc
