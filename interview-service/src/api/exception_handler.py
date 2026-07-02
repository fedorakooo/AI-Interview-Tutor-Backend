from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from jwt_handler.exceptions.token_errors import TokenError


def exception_container(app: FastAPI) -> None:
    @app.exception_handler(TokenError)
    async def token_exception_handler(request: Request, exc: TokenError):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": str(exc)},
        )
