class ReportError(Exception):
    pass


class ReportNotReadyError(ReportError):
    pass


class FocusNotFoundError(ReportError):
    pass
