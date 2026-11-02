class SpecDraftError(Exception):
    pass


class EmptySpecDraftError(SpecDraftError):
    pass


class SpecDraftGenerationError(SpecDraftError):
    pass
