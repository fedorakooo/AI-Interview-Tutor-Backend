from pydantic import BaseModel, SecretStr, field_validator

from src.api.v1.models.validators.user_validators import PasswordValidator


class ResetPasswordRequest(BaseModel):
    new_password: SecretStr

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value: SecretStr) -> SecretStr:
        return PasswordValidator.validate(value)


class PasswordResetTokenResponse(BaseModel):
    password_reset_token: str
