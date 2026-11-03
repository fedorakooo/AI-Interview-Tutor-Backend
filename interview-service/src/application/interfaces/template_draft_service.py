from abc import ABC, abstractmethod

from shared_models.assessment import TemplateDraftRequest

from src.application.dtos.template_draft import TemplateDraft


class ITemplateDraftService(ABC):
    """Use case of drafting an interview template from recruiter text."""

    @abstractmethod
    async def create(self, request: TemplateDraftRequest) -> TemplateDraft:
        """Draft a valid interview template from the recruiter text."""
