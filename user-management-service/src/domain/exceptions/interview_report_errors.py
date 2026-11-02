class InterviewReportError(Exception):
    pass


class InterviewReportNotFoundError(InterviewReportError):
    pass


class InterviewReportNotReadyError(InterviewReportError):
    pass


class InterviewReportUnavailableError(InterviewReportError):
    pass
