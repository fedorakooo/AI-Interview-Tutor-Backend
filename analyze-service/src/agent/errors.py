class CVParserException(Exception):
    """Custom exception for errors during CV parsing."""

    pass


class ModelOutputParsingException(CVParserException):
    """Raised when the LLM's output cannot be parsed into the target schema."""

    pass
