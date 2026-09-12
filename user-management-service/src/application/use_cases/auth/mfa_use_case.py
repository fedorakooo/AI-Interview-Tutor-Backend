"""TOTP-style MFA scaffold for admin accounts."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from uuid import UUID

from src.domain.exceptions.not_found_error import NotFoundError
from src.domain.interfaces.database.uow import IUnitOfWork
from src.domain.value_objects.user_role import UserRole


def _generate_totp_secret() -> str:
    try:
        import pyotp

        return pyotp.random_base32()
    except ImportError:
        return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _verify_totp(secret: str, code: str, *, window: int = 1) -> bool:
    normalized = code.strip().replace(" ", "")
    if not normalized.isdigit() or len(normalized) != 6:
        return False
    try:
        import pyotp

        totp = pyotp.TOTP(secret)
        return totp.verify(normalized, valid_window=window)
    except ImportError:
        return _verify_totp_hmac(secret, normalized, window=window)


def _verify_totp_hmac(secret: str, code: str, *, window: int = 1) -> bool:
    """RFC6238-style HMAC fallback when pyotp is unavailable."""
    key = base64.b32decode(secret.upper() + "=" * ((8 - len(secret) % 8) % 8))
    now = int(time.time()) // 30
    for offset in range(-window, window + 1):
        counter = struct.pack(">Q", now + offset)
        digest = hmac.new(key, counter, hashlib.sha1).digest()
        start = digest[-1] & 0x0F
        value = struct.unpack(">I", digest[start : start + 4])[0] & 0x7FFFFFFF
        if f"{value % 1_000_000:06d}" == code:
            return True
    return False


class SetupMfaUseCase:
    """Generate and persist an MFA secret for an admin user."""

    def __init__(self, uow: IUnitOfWork) -> None:
        self._uow = uow

    async def __call__(self, user_id: UUID) -> dict[str, str]:
        async with self._uow:
            user = await self._uow.user_repository.get_by_id(user_id)
            if user is None:
                raise NotFoundError(f"User {user_id} not found")
            if user.role != UserRole.ADMIN:
                raise PermissionError("MFA setup is restricted to admin accounts")

            secret = _generate_totp_secret()
            user.mfa_secret = secret
            await self._uow.user_repository.update(user)

        issuer = "AI-Interview-Tutor"
        otpauth_uri = f"otpauth://totp/{issuer}:{user.email}?secret={secret}&issuer={issuer}&digits=6"
        return {"secret": secret, "otpauth_uri": otpauth_uri}


class VerifyMfaUseCase:
    """Verify a TOTP code against the stored MFA secret."""

    def __init__(self, uow: IUnitOfWork) -> None:
        self._uow = uow

    async def __call__(self, user_id: UUID, code: str) -> bool:
        async with self._uow:
            user = await self._uow.user_repository.get_by_id(user_id)
            if user is None:
                raise NotFoundError(f"User {user_id} not found")
            if not user.mfa_secret:
                raise ValueError("MFA is not configured for this account")
            return _verify_totp(user.mfa_secret, code)
