"""Team / org accounts stub (FEATURE_TEAM_ORGS)."""

from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from jwt_handler.value_objects import AccessTokenPayload
from pydantic import BaseModel, EmailStr, Field
from shared_models.feature_flags.flags import feature_enabled

from src.api.security import require_authenticated

router = APIRouter(prefix="/orgs", tags=["Organizations"])

_ORGS: dict[str, dict] = {}


class OrgCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    seats: int = Field(default=5, ge=1, le=500)


class OrgMember(BaseModel):
    email: EmailStr
    role: str = "member"


class OrgView(BaseModel):
    org_id: str
    name: str
    seats: int
    owner_user_id: str
    members: list[OrgMember] = Field(default_factory=list)


def _require_feature() -> None:
    if not feature_enabled("TEAM_ORGS", False):
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Team orgs are disabled")


@router.post("", response_model=OrgView, status_code=201)
async def create_org(
    body: OrgCreate,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
) -> OrgView:
    _require_feature()
    org_id = str(uuid4())
    org = {
        "org_id": org_id,
        "name": body.name,
        "seats": body.seats,
        "owner_user_id": payload["id"],
        "members": [],
    }
    _ORGS[org_id] = org
    return OrgView.model_validate(org)


@router.get("/mine", response_model=list[OrgView])
async def list_my_orgs(
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
) -> list[OrgView]:
    _require_feature()
    uid = payload["id"]
    return [
        OrgView.model_validate(org)
        for org in _ORGS.values()
        if org["owner_user_id"] == uid or any(m.get("user_id") == uid for m in org.get("members", []))
    ]


@router.post("/{org_id}/members", response_model=OrgView)
async def invite_member(
    org_id: str,
    body: OrgMember,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
) -> OrgView:
    _require_feature()
    org = _ORGS.get(org_id)
    if not org or org["owner_user_id"] != payload["id"]:
        raise HTTPException(status_code=404, detail="Organization not found")
    if len(org["members"]) + 1 >= org["seats"]:
        raise HTTPException(status_code=400, detail="No seats remaining")
    org["members"].append(body.model_dump())
    return OrgView.model_validate(org)
