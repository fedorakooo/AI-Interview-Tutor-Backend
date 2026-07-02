from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).parent
SOFT_QUESTIONS_JSON_PATH = BASE_DIR / "data" / "soft_questions.json"


class LLMProvider(str, Enum):
    OPENAI = "openai"
    OPENROUTER = "openrouter"
    GOOGLE = "google"


class LLMConfig(BaseSettings):
    model: str
    temperature: float = 0.6
    api_base: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class MongoSettings(BaseSettings):
    host: str = "mongodb"
    port: int = 27017
    user: str = "app"
    password: str = "app"
    auth_source: str = "ai_interview"
    db_name: str = "ai_interview"
    cv_analysis_collection_name: str = "cv_analysis"
    cv_user_id_field: str = "user_id"

    @property
    def url(self) -> str:
        return (
            f"mongodb://{self.user}:{self.password}@{self.host}:{self.port}/"
            f"{self.db_name}?authSource={self.auth_source}"
        )

    model_config = SettingsConfigDict(env_prefix="MONGODB_", env_file=".env", extra="ignore")


class JWTSettings(BaseSettings):
    public_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class AppSettings(BaseSettings):
    port: int = 8001

    model_config = SettingsConfigDict(env_prefix="INTERVIEW_SERVICE_", env_file=".env", extra="ignore")


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


class Settings(BaseSettings):
    environment: str = "development"
    debug: bool = True
    cors_allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://localhost"])

    llm_provider: LLMProvider = LLMProvider.OPENAI

    openai_api_key: str = ""
    openai_llm: LLMConfig = Field(default_factory=lambda: LLMConfig(model="gpt-4o-mini"))

    openrouter_api_key: str = ""
    openrouter_llm: LLMConfig = Field(
        default_factory=lambda: LLMConfig(
            model="openai/gpt-4o-mini",
            api_base="https://openrouter.ai/api/v1",
        )
    )

    google_api_key: str = ""
    google_llm: LLMConfig = Field(default_factory=lambda: LLMConfig(model="gemini-2.0-flash"))

    interview_llm_temperature: float | None = Field(default=None, validation_alias="INTERVIEW_LLM__TEMPERATURE")

    logger_settings: LoggerSettings = LoggerSettings()
    app_settings: AppSettings = AppSettings()
    mongo_settings: MongoSettings = MongoSettings()
    jwt_settings: JWTSettings = JWTSettings()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
    )

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
