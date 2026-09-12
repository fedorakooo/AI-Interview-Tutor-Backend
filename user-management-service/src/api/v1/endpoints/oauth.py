"""OAuth (Google / GitHub) — returns 501 when client credentials are not configured."""

from __future__ import annotations

import secrets
import uuid
from typing import Annotated
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from jwt_handler.dtos import TokenInfoDTO
from jwt_handler.interfaces import IAccessTokenGenerator, IRefreshTokenGenerator
from jwt_handler.models import TokenResponse
from jwt_handler.value_objects import AuthType
from pydantic import BaseModel

from src.api.dependencies.auth import (
    get_access_token_generator,
    get_password_handler,
    get_refresh_token_generator,
)
from src.api.dependencies.database import get_unit_of_work
from src.application.dtos.user import UserCreateDTO
from src.application.mappers.user_mapper import UserMapper
from src.config import settings
from src.domain.interfaces.auth.password_handler import IPasswordHandler
from src.domain.interfaces.database.uow import IUnitOfWork
from src.domain.value_objects.user_role import UserRole

router = APIRouter(prefix="/auth/oauth", tags=["OAuth"])

_STATE_STORE: dict[str, str] = {}


class OAuthCallbackBody(BaseModel):
    code: str
    state: str


def _provider_config(provider: str) -> dict[str, str] | None:
    provider = provider.lower()
    oauth = settings.oauth_settings
    if provider == "google":
        if not oauth.google_configured:
            return None
        return {
            "client_id": oauth.google_oauth_client_id,
            "client_secret": oauth.google_oauth_client_secret,
            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "userinfo_url": "https://www.googleapis.com/oauth2/v3/userinfo",
            "scope": "openid email profile",
        }
    if provider == "github":
        if not oauth.github_configured:
            return None
        return {
            "client_id": oauth.github_oauth_client_id,
            "client_secret": oauth.github_oauth_client_secret,
            "auth_url": "https://github.com/login/oauth/authorize",
            "token_url": "https://github.com/login/oauth/access_token",
            "userinfo_url": "https://api.github.com/user",
            "scope": "read:user user:email",
        }
    return None


def _build_start_response(provider: str, cfg: dict[str, str]) -> dict[str, str]:
    redirect_uri = settings.frontend_settings.oauth_callback_url
    state = secrets.token_urlsafe(24)
    _STATE_STORE[state] = provider.lower()
    params = {
        "client_id": cfg["client_id"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": cfg["scope"],
        "state": state,
    }
    return {"authorization_url": f"{cfg['auth_url']}?{urlencode(params)}", "state": state}


async def _exchange_code_for_tokens(
    provider: str,
    cfg: dict[str, str],
    code: str,
    state: str,
    uow: IUnitOfWork,
    access_token_generator: IAccessTokenGenerator,
    refresh_token_generator: IRefreshTokenGenerator,
    password_handler: IPasswordHandler,
) -> TokenResponse:
    if _STATE_STORE.pop(state, None) != provider.lower():
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    redirect_uri = settings.frontend_settings.oauth_callback_url
    async with httpx.AsyncClient(timeout=20.0) as client:
        token_resp = await client.post(
            cfg["token_url"],
            data={
                "client_id": cfg["client_id"],
                "client_secret": cfg["client_secret"],
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
        )
        if token_resp.status_code >= 400:
            raise HTTPException(status_code=400, detail="OAuth token exchange failed")
        token_payload = token_resp.json()
        access = token_payload.get("access_token")
        headers = {"Authorization": f"Bearer {access}", "Accept": "application/json"}
        user_resp = await client.get(cfg["userinfo_url"], headers=headers)
        if user_resp.status_code >= 400:
            raise HTTPException(status_code=400, detail="Failed to fetch OAuth profile")
        profile = user_resp.json()

        email = profile.get("email")
        if not email and provider.lower() == "github":
            emails_resp = await client.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"Bearer {access}", "Accept": "application/json"},
            )
            if emails_resp.status_code < 400:
                for item in emails_resp.json():
                    if item.get("primary") and item.get("email"):
                        email = item["email"]
                        break
    if not email:
        raise HTTPException(status_code=400, detail="OAuth provider did not return an email")

    username = profile.get("login") or profile.get("name") or email.split("@")[0]
    username = str(username).replace(" ", "_")[:32]

    async with uow:
        user = await uow.user_repository.get_by_email(email)
        if user is None:
            create = UserCreateDTO(
                first_name=str(profile.get("given_name") or profile.get("name") or "OAuth"),
                second_name=str(profile.get("family_name") or "User"),
                username=username,
                phone_number=f"+1000{uuid.uuid4().int % 10_000_000:07d}",
                password=secrets.token_urlsafe(24),
                email=email,
            )
            entity = UserMapper.from_create_dto_to_entity(
                user_create=create,
                user_id=uuid.uuid4(),
                hashed_password=password_handler.hash_password(create.password),
                user_role=UserRole.USER,
                is_blocked=False,
            )
            entity.is_email_verified = True
            user = await uow.user_repository.create(entity)
        elif user.is_blocked:
            raise HTTPException(status_code=403, detail="User is blocked")

    token_info = TokenInfoDTO(
        access_token=access_token_generator.generate_access_token(
            user_id=str(user.id),
            username=user.username,
            user_role=user.role,
            is_blocked=user.is_blocked,
        ),
        refresh_token=refresh_token_generator.generate_refresh_token(
            user_id=str(user.id),
            username=user.username,
        ),
        auth_type=AuthType.BEARER,
    )
    return TokenResponse.from_dto(token_info)


@router.get("/{provider}")
@router.post("/{provider}")
async def oauth_start(provider: str) -> dict[str, str]:
    cfg = _provider_config(provider)
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"OAuth provider '{provider}' is not configured (set provider client id/secret env vars)",
        )
    return _build_start_response(provider.lower(), cfg)


@router.get("/{provider}/start")
@router.post("/{provider}/start")
async def oauth_start_explicit(provider: str) -> dict[str, str]:
    return await oauth_start(provider)


@router.get("/{provider}/callback", response_model=TokenResponse)
async def oauth_callback_get(
    provider: str,
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    access_token_generator: Annotated[IAccessTokenGenerator, Depends(get_access_token_generator)],
    refresh_token_generator: Annotated[IRefreshTokenGenerator, Depends(get_refresh_token_generator)],
    password_handler: Annotated[IPasswordHandler, Depends(get_password_handler)],
    code: str = Query(...),
    state: str = Query(...),
) -> TokenResponse:
    cfg = _provider_config(provider)
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"OAuth provider '{provider}' is not configured",
        )
    return await _exchange_code_for_tokens(
        provider.lower(),
        cfg,
        code,
        state,
        uow,
        access_token_generator,
        refresh_token_generator,
        password_handler,
    )


@router.post("/{provider}/callback", response_model=TokenResponse)
async def oauth_callback_post(
    provider: str,
    body: OAuthCallbackBody,
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    access_token_generator: Annotated[IAccessTokenGenerator, Depends(get_access_token_generator)],
    refresh_token_generator: Annotated[IRefreshTokenGenerator, Depends(get_refresh_token_generator)],
    password_handler: Annotated[IPasswordHandler, Depends(get_password_handler)],
) -> TokenResponse:
    cfg = _provider_config(provider)
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"OAuth provider '{provider}' is not configured",
        )
    return await _exchange_code_for_tokens(
        provider.lower(),
        cfg,
        body.code,
        body.state,
        uow,
        access_token_generator,
        refresh_token_generator,
        password_handler,
    )
