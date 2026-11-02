class FeedbackError(Exception):
    pass


class FeedbackDisabledError(FeedbackError):
    pass


class FeedbackLeakError(FeedbackError):
    pass
