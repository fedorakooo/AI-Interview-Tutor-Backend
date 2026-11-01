import bcrypt

from src.domain.interfaces.auth.password_handler import IPasswordHandler


class PasswordHandler(IPasswordHandler):
    def hash_password(self, password: str) -> str:
        if len(password.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 UTF-8 bytes")
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode(), salt).decode("utf-8")

    def validate_password(self, password: str, hashed_password: str) -> bool:
        if len(password.encode("utf-8")) > 72:
            return False
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
