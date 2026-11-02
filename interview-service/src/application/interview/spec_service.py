from shared_models.assessment import AssessmentTemplateSnapshot, TemplateDraftRequest

from src.domain.interfaces.spec_drafter import ISpecDrafter
from src.domain.interview.spec_builder import build_template


class SpecDraftService:
    def __init__(self, drafter: ISpecDrafter) -> None:
        self._drafter = drafter

    async def create_draft(self, request: TemplateDraftRequest) -> AssessmentTemplateSnapshot:
        return build_template(await self._drafter.draft(request), request)
