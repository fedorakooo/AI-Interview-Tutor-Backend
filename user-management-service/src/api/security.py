from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, OAuth2PasswordBearer
from jwt_handler.exceptions import InvalidTokenError
from jwt_handler.interfaces import ITokenHandler
from jwt_handler.value_objects import AccessTokenPayload, TokenType

from src.api.dependencies.auth import get_token_handler
from src.api.dependencies.database import get_unit_of_work
from src.domain.entities.organization import OrganizationMember
from src.domain.exceptions.not_found_error import NotFoundError
from src.domain.exceptions.organization_errors import OrganizationAccessError
from src.domain.exceptions.user_errors import UserBlockedError
from src.domain.interfaces.database.uow import IUnitOfWork
from src.domain.value_objects.organization_role import OrganizationRole
from src.domain.value_objects.user_role import UserRole

http_bearer = HTTPBearer(auto_error=False)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/token",
)


async def get_access_token_payload(
    token_handler: Annotated[ITokenHandler, Depends(get_token_handler)],
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    token: str = Depends(oauth2_scheme),
) -> AccessTokenPayload:
    payload = token_handler.decode_jwt(token)
    if payload.get("type") != TokenType.ACCESS:
        raise InvalidTokenError("Invalid access token")
    try:
        user_id = UUID(payload["id"])
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise InvalidTokenError("Invalid access token") from exc
    async with uow:
        user = await uow.user_repository.get_by_id(user_id)
    if user is None:
        raise InvalidTokenError("Invalid access token")
    if user.is_blocked or payload.get("is_blocked"):
        raise UserBlockedError(user.username)
    version = payload.get("auth_version", 0)
    if type(version) is not int or version != user.auth_version:
        raise InvalidTokenError("Invalid access token")
    # Authorization uses current database state, including role demotions.
    return {**payload, "role": user.role, "username": user.username, "is_blocked": user.is_blocked}


async def require_authenticated(
    payload: Annotated[AccessTokenPayload, Depends(get_access_token_payload)],
) -> AccessTokenPayload:
    # Refresh credentials are only valid at the refresh endpoint.  Treating
    # them as bearer credentials would extend their authority to every
    # protected API.
    if payload.get("type") != TokenType.ACCESS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")
    if payload.get("is_blocked"):
        raise UserBlockedError(payload["username"])
    return payload


def require_roles(*roles: UserRole):
    async def _check(
        payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    ) -> AccessTokenPayload:
        if payload["role"] not in {role.value for role in roles}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return payload

    return _check


def require_org_role(*allowed_roles: OrganizationRole):
    """Require an active, current organization membership from PostgreSQL.

    ``organization_id`` is deliberately part of the SQL predicate rather than
    trusted just because it appears in a path parameter.
    """

    async def _check(
        organization_id: UUID,
        payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
        uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    ) -> OrganizationMember:
        try:
            user_id = UUID(payload["id"])
        except (KeyError, ValueError) as exc:
            raise NotFoundError("Organization not found") from exc

        async with uow:
            membership = await uow.organization_repository.get_member(organization_id, user_id)
        if membership is None or membership.status != "active":
            raise NotFoundError("Organization not found")
        if membership.role not in allowed_roles:
            raise OrganizationAccessError()
        return membership

    return _check
