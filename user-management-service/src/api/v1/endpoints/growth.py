"""Growth loops: referrals backed by Postgres with in-memory fallback."""

from __future__ import annotations

import secrets
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from jwt_handler.value_objects import AccessTokenPayload
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.database import get_session
from src.api.security import require_authenticated
from src.infrastructure.postgres.schemas.referral import ReferralCodeORM

router = APIRouter(prefix="/growth", tags=["Growth"])

_REFERRALS: dict[str, dict] = {}
_WAITLIST: list[dict] = []


class ReferralCode(BaseModel):
    code: str
    credits: int = 0


class WaitlistRequest(BaseModel):
    email: EmailStr
    role: str | None = Field(default=None, max_length=64)


@router.post("/referral", response_model=ReferralCode)
async def create_referral(
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReferralCode:
    code = secrets.token_urlsafe(6).upper()
    owner_id = UUID(str(payload["id"]))
    try:
        session.add(ReferralCodeORM(code=code, owner_user_id=owner_id, credits=0, redemptions=0))
        await session.commit()
    except Exception:
        await session.rollback()
        _REFERRALS[code] = {"owner_user_id": str(owner_id), "credits": 0, "redemptions": 0}
    return ReferralCode(code=code, credits=0)


@router.post("/referral/{code}/redeem")
async def redeem_referral(
    code: str,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, str]:
    normalized = code.upper()
    result = await session.execute(select(ReferralCodeORM).where(ReferralCodeORM.code == normalized))
    entry = result.scalar_one_or_none()
    if entry is None:
        mem = _REFERRALS.get(normalized)
        if not mem:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invalid code")
        if mem["owner_user_id"] == payload["id"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cannot redeem own code")
        mem["redemptions"] += 1
        mem["credits"] += 1
        return {"detail": "ok"}
    if str(entry.owner_user_id) == payload["id"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cannot redeem own code")
    entry.redemptions += 1
    entry.credits += 1
    await session.commit()
    return {"detail": "ok"}


@router.post("/waitlist")
async def join_waitlist(body: WaitlistRequest) -> dict[str, str]:
    _WAITLIST.append(body.model_dump())
    return {"detail": "joined"}


async def apply_referral_on_signup(session: AsyncSession, code: str, new_user_id: UUID) -> None:
    normalized = code.upper()
    result = await session.execute(select(ReferralCodeORM).where(ReferralCodeORM.code == normalized))
    entry = result.scalar_one_or_none()
    if entry is None or entry.owner_user_id == new_user_id:
        return
    entry.redemptions += 1
    entry.credits += 1
    await session.commit()
