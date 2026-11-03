from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from jwt_handler.exceptions.token_errors import TokenError

from src.api.errors.error_mapping import resolve_error_spec
from src.domain.exceptions.interview_service_error import InterviewServiceError


def exception_container(app: FastAPI) -> None:
    @app.exception_handler(InterviewServiceError)
    async def handle_service_error(request: Request, exc: InterviewServiceError) -> JSONResponse:
        spec = resolve_error_spec(exc)
        return JSONResponse(status_code=spec.http_status, content={"detail": spec.detail})

    @app.exception_handler(TokenError)
    async def handle_token_error(request: Request, exc: TokenError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": str(exc)})
