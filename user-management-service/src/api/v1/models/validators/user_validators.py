import re

from pydantic import SecretStr


class NameValidator:
    @staticmethod
    def validate(v: str) -> str:
        v = v.strip()
        if not (3 <= len(v) <= 30):
            raise ValueError("Name must be between 3 and 30 characters")
        if not re.match(r"^[a-zA-Zа-яА-ЯёЁ\-\'\s]+$", v):
            raise ValueError("Name contains invalid characters.")
        return v


class UsernameValidator:
    @staticmethod
    def validate(v: str) -> str:
        v = v.strip()
        if not (4 <= len(v) <= 30):
            raise ValueError("Username must be between 4 and 30 characters")
        if not re.match(r"^[a-zA-Z0-9_\.]+$", v):
            raise ValueError("Username can only contain letters, digits, underscores, and dots")
        if v[0] in "._" or v[-1] in "._":
            raise ValueError("Username cannot start or end with '.' or '_'")
        if re.search(r"[._]{2,}", v):
            raise ValueError("Username cannot contain consecutive '.' or '_'")
        return v


class PhoneValidator:
    @staticmethod
    def validate(v: str) -> str:
        v = re.sub(r"[^\d+]", "", v)
        if len(v) < 10:
            raise ValueError("Invalid phone number format")
        if not re.match(r"^\+?\d{10,15}$", v):
            raise ValueError("Must be 10-15 digits with optional '+' prefix")
        return v


class PasswordValidator:
    @staticmethod
    def validate(v: SecretStr) -> SecretStr:
        password = v.get_secret_value()
        if not (8 <= len(password) <= 128):
            raise ValueError("Password must be between 8 and 128 characters")
        if len(password.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 UTF-8 bytes")
        if not re.search(r"\d", password):
            raise ValueError("Password must contain at least one digit")
        return v
