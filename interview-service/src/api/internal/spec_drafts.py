from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import ValidationError
from shared_models.assessment import AssessmentTemplateSnapshot, TemplateDraftRequest

from src.api.internal.auth import require_internal_service
from src.application.interview.spec_service import SpecDraftService
from src.domain.interview.spec_builder import EmptySpecDraftError
from src.logger import app_logger

router = APIRouter(
    prefix="/api/internal/spec-drafts",
    tags=["Internal specification"],
    dependencies=[Depends(require_internal_service)],
)


def get_spec_service(request: Request) -> SpecDraftService:
    return request.app.state.spec_draft_service


@router.post("", response_model=AssessmentTemplateSnapshot)
async def create_spec_draft(
    body: TemplateDraftRequest,
    service: Annotated[SpecDraftService, Depends(get_spec_service)],
) -> AssessmentTemplateSnapshot:
    try:
        return await service.create_draft(body)
    except (EmptySpecDraftError, ValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No usable draft produced"
        ) from exc
    except Exception as exc:
        app_logger.exception("Creating a specification draft failed")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Draft generation failed") from exc
