from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from shared_models.assessment import AssessmentTemplateSnapshot

from src.domain.exceptions.assessment_context_errors import (
    AssessmentContextNotFoundError,
    AssessmentContextUnavailableError,
    AssessmentNotReadyError,
)
from src.domain.interfaces.assessment_context_client import IAssessmentContextClient


def get_context_client(request: Request) -> IAssessmentContextClient:
    return request.app.state.assessment_context_client


ContextClientDep = Annotated[IAssessmentContextClient, Depends(get_context_client)]


async def template_for_attempt(
    context_client: IAssessmentContextClient, attempt_id: UUID
) -> AssessmentTemplateSnapshot:
    try:
        return (await context_client.get_context(attempt_id)).template
    except AssessmentContextNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found") from exc
    except AssessmentNotReadyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Report is not ready") from exc
    except AssessmentContextUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Context unavailable") from exc
