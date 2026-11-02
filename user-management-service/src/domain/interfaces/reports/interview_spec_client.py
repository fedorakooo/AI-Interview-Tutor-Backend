from abc import ABC, abstractmethod

from shared_models.assessment import AssessmentTemplateSnapshot, TemplateDraftRequest


class IInterviewSpecClient(ABC):
    @abstractmethod
    async def create_template_draft(self, request: TemplateDraftRequest) -> AssessmentTemplateSnapshot:
        """Ask the interview service to draft a template from the recruiter text."""
