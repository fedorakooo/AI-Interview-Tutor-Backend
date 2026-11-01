import hashlib
import hmac
import secrets


class InvitationTokenHandler:
    """Generates opaque links and persists only a peppered SHA-256 digest."""

    def __init__(self, pepper: str):
        if not pepper:
            raise ValueError("ASSESSMENT_INVITATION_TOKEN_PEPPER must be configured")
        self._pepper = pepper.encode()

    def generate(self) -> str:
        # 32 random bytes provides 256 bits of entropy before URL-safe encoding.
        return secrets.token_urlsafe(32)

    def hash(self, token: str) -> str:
        return hmac.new(self._pepper, token.encode(), hashlib.sha256).hexdigest()

    def matches(self, token: str, expected_hash: str) -> bool:
        return hmac.compare_digest(self.hash(token), expected_hash)
