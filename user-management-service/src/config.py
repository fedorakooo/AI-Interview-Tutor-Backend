from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PostgresSettings(BaseSettings):
    """Postgres connection settings."""

    user: str
    host: str
    port: str
    name: str
    password: str

    @property
    def url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}" f"@{self.host}:{self.port}/{self.name}"

    model_config = SettingsConfigDict(env_prefix="POSTGRES_", env_file=".env", extra="ignore")


class SQLAlchemySettings(BaseSettings):
    """SQLAlchemy configuration settings."""

    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10
    expire_on_commit: bool = False


class LoggerSettings(BaseSettings):
    """Logging configuration settings."""

    logging_config: dict[str, Any] = {}

    @classmethod
    def load_from_yaml(cls, file_path: str = "config.yaml") -> dict[str, Any]:
        """Load logging configuration from YAML file."""
        path = Path(file_path)
        if not path.exists():
            return {}

        with path.open() as f:
            config = yaml.safe_load(f)
            return config.get("logger", {})


class RedisSettings(BaseSettings):
    """Redis connection settings."""

    port: str
    host: str
    password: str
    user: str
    user_password: str

    decode_responses: bool = True

    model_config = SettingsConfigDict(env_prefix="REDIS_", env_file=".env", extra="ignore")


class JWTSettings(BaseSettings):
    """JWT settings."""

    public_key: str
    private_key: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class FrontendSettings(BaseSettings):
    """Frontend URLs used in outbound notification payloads."""

    reset_password_url: str = "http://localhost:3000/reset-password"

    model_config = SettingsConfigDict(env_prefix="FRONTEND_", env_file=".env", extra="ignore")


class RabbitMQSettings(BaseSettings):
    """RabbitMQ connection settings."""

    port: int
    host: str
    user: str
    password: str

    cv_analyzer_queue_name: str = "cv-analyze-stream"
    reset_password_queue_name: str = "reset-password-stream"

    timeout: float = 30

    @property
    def url(self) -> str:
        return f"amqp://{self.user}:{self.password}@{self.host}:{self.port}/"

    model_config = SettingsConfigDict(env_prefix="RABBITMQ_", env_file=".env", extra="ignore")


class Settings(BaseSettings):
    """Application settings container."""

    environment: str = "development"
    debug: bool = True
    cors_allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://localhost"])

    postgres_settings: PostgresSettings = PostgresSettings()
    sql_alchemy_settings: SQLAlchemySettings = SQLAlchemySettings()
    logger_settings: LoggerSettings = LoggerSettings()
    jwt_settings: JWTSettings = JWTSettings()
    redis_settings: RedisSettings = RedisSettings()
    rabbitmq_settings: RabbitMQSettings = RabbitMQSettings()
    frontend_settings: FrontendSettings = FrontendSettings()

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    def __init__(self) -> None:
        super().__init__()
        self.logger_settings.logging_config = LoggerSettings.load_from_yaml()


settings = Settings()
