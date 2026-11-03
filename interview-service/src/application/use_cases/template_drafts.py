import logging

from pydantic import ValidationError
from shared_models.assessment import AssessmentTemplateSnapshot, TemplateDraftRequest

from src.domain.exceptions.spec_errors import EmptySpecDraftError, SpecDraftError, SpecDraftGenerationError
from src.domain.interfaces.spec_drafter import ISpecDrafter
from src.domain.interview.spec_builder import build_template

logger = logging.getLogger(__name__)


class CreateTemplateDraftUseCase:
    def __init__(self, drafter: ISpecDrafter):
        self._drafter = drafter

    async def __call__(self, request: TemplateDraftRequest) -> AssessmentTemplateSnapshot:
        try:
            return build_template(await self._drafter.draft(request), request)
        except ValidationError as exc:
            raise EmptySpecDraftError() from exc
        except SpecDraftError:
            raise
        except Exception as exc:
            logger.exception("Creating a specification draft failed")
            raise SpecDraftGenerationError() from exc
