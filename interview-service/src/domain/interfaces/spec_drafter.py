from abc import ABC, abstractmethod

from shared_models.assessment import TemplateDraftRequest

from src.domain.interview.spec_dto import SpecDraft


class ISpecDrafter(ABC):
    """LLM port for drafting interview specifications from recruiter text."""

    @abstractmethod
    async def draft(self, request: TemplateDraftRequest) -> SpecDraft:
        """Turn the recruiter text and job description into a draft interview specification."""
