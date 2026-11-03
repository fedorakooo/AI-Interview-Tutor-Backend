import logging

from shared_models.assessment import TemplateDraftRequest

from src.application.dtos.template_draft import TemplateDraft
from src.application.interfaces.template_draft_service import ITemplateDraftService
from src.application.mappers.template_draft_mapper import TemplateDraftMapper
from src.domain.exceptions.invalid_value_errors import InvalidDomainValueError
from src.domain.exceptions.spec_errors import EmptySpecDraftError, SpecDraftError, SpecDraftGenerationError
from src.domain.interfaces.ai.spec_drafter import ISpecDrafter
from src.domain.services.template_builder import TemplateBuilder

logger = logging.getLogger(__name__)


class TemplateDraftService(ITemplateDraftService):
    def __init__(self, drafter: ISpecDrafter) -> None:
        self._drafter = drafter

    async def create(self, request: TemplateDraftRequest) -> TemplateDraft:
        brief = TemplateDraftMapper.to_brief(request)
        try:
            template = TemplateBuilder.build(await self._drafter.draft(brief), brief)
        except InvalidDomainValueError as exc:
            raise EmptySpecDraftError() from exc
        except SpecDraftError:
            raise
        except Exception as exc:
            logger.exception("Creating a specification draft failed")
            raise SpecDraftGenerationError() from exc
        return TemplateDraftMapper.to_dto(template)
