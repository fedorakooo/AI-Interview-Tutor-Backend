class SessionError(Exception):
    pass


class SessionCompletedError(SessionError):
    pass


class SessionBusyError(SessionError):
    pass


class NoPendingQuestionError(SessionError):
    pass


class EventSeqConflictError(SessionError):
    pass
