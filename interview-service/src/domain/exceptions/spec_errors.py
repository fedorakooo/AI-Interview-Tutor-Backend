class SpecDraftError(Exception):
    """Base exception for interview specification draft errors."""


class EmptySpecDraftError(SpecDraftError):
    """Raised when the model draft has no usable focus areas or fails validation."""


class SpecDraftGenerationError(SpecDraftError):
    """Raised when the model fails to generate a specification draft."""
