from fastapi import APIRouter, Depends
from shared_models.assessment import AssessmentTemplateSnapshot, TemplateDraftRequest

from src.api.dependencies.container import ContainerDep
from src.api.mappers.template_draft_mapper import TemplateDraftMapper
from src.api.security import require_internal_service

router = APIRouter(
    prefix="/api/internal/spec-drafts",
    tags=["Internal specification"],
    dependencies=[Depends(require_internal_service)],
)


@router.post("", response_model=AssessmentTemplateSnapshot)
async def create_spec_draft(body: TemplateDraftRequest, container: ContainerDep) -> AssessmentTemplateSnapshot:
    return TemplateDraftMapper.to_snapshot(await container.template_draft_service.create(body))
