class AssessmentContextError(Exception):
    pass


class AssessmentContextNotFoundError(AssessmentContextError):
    pass


class AssessmentNotReadyError(AssessmentContextError):
    pass


class AssessmentContextUnavailableError(AssessmentContextError):
    pass
