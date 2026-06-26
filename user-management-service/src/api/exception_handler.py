from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from jwt_handler.exceptions.token_errors import TokenError

from src.domain.exceptions.login_errors import LoginError
from src.domain.exceptions.not_found_error import NotFoundError
from src.domain.exceptions.user_errors import UserBlockedError
from src.infrastructure.logger.logger import logger
from src.infrastructure.postgres.exceptions.database_errors import DatabaseError, DatabaseUniqueViolationError


def exception_container(app: FastAPI) -> None:
    @app.exception_handler(LoginError)
    async def login_exception_handler(request: Request, exc: LoginError):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid password or login"},
        )

    @app.exception_handler(TokenError)
    async def token_exception_handler(request: Request, exc: TokenError):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": str(exc)},
        )

    @app.exception_handler(UserBlockedError)
    async def user_blocked_exception_handler(request: Request, exc: UserBlockedError):
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": str(exc)})

    @app.exception_handler(NotFoundError)
    def not_found_exception_handler(request: Request, exc: NotFoundError):
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})

    @app.exception_handler(DatabaseUniqueViolationError)
    def database_unique_validation_exception_handler(request: Request, exc: DatabaseUniqueViolationError):
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)})

    @app.exception_handler(DatabaseError)
    def database_error_handler(request: Request, exc: DatabaseError):
        logger.error(f"Database error: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred"},
        )

    @app.exception_handler(Exception)
    async def server_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unexpected server error: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred"},
        )
