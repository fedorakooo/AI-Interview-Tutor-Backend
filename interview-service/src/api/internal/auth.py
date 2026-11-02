import hmac
from typing import Annotated

from fastapi import Header, HTTPException, status

from src.config import settings


async def require_internal_service(
    token: Annotated[str | None, Header(alias="X-Internal-Service-Token")] = None,
) -> None:
    configured = settings.internal_service_token
    if not configured or token is None or not hmac.compare_digest(token, configured):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal credentials")
