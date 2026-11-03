from abc import ABC, abstractmethod

from src.domain.value_objects.draft_brief import DraftBrief
from src.domain.value_objects.spec_draft import SpecDraft


class ISpecDrafter(ABC):
    """LLM port for drafting interview specifications from recruiter text."""

    @abstractmethod
    async def draft(self, request: DraftBrief) -> SpecDraft:
        """Turn the recruiter text and job description into a draft interview specification."""
