from uuid import UUID

from fastapi import APIRouter, Depends
from shared_models.assessment import ErasureRequest, ErasureResult

from src.api.dependencies.container import ContainerDep
from src.api.security import require_internal_service

router = APIRouter(
    prefix="/api/internal/erasure",
    tags=["Internal erasure"],
    dependencies=[Depends(require_internal_service)],
)


@router.post("/{attempt_id}", response_model=ErasureResult)
async def erase_attempt_data(attempt_id: UUID, body: ErasureRequest, container: ContainerDep) -> ErasureResult:
    return await container.data_erasure_service.erase(attempt_id, body.cv_correlation_id)
