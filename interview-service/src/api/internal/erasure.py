from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from shared_models.assessment import ErasureRequest, ErasureResult

from src.api.internal.auth import require_internal_service
from src.application.interview.erasure_service import AttemptErasureService
from src.domain.exceptions.session_errors import SessionBusyError

router = APIRouter(
    prefix="/api/internal/erasure",
    tags=["Internal erasure"],
    dependencies=[Depends(require_internal_service)],
)


def get_erasure_service(request: Request) -> AttemptErasureService:
    return request.app.state.attempt_erasure_service


@router.post("/{attempt_id}", response_model=ErasureResult)
async def erase_attempt_data(
    attempt_id: UUID,
    body: ErasureRequest,
    service: Annotated[AttemptErasureService, Depends(get_erasure_service)],
) -> ErasureResult:
    try:
        return await service.erase(attempt_id, body.cv_correlation_id)
    except SessionBusyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Interview is in progress") from exc
