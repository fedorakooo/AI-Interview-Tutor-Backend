from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).parent
SOFT_QUESTIONS_JSON_PATH = BASE_DIR / "data" / "soft_questions.json"


class LLMConfig(BaseSettings):
    model: str
    temperature: float = 0.6
    api_base: str | None = None
    api_key: str | None = None

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
    logger_settings: LoggerSettings = LoggerSettings()
    app_settings: AppSettings = AppSettings()
    mongo_settings: MongoSettings = MongoSettings()
    google_llm: LLMConfig = LLMConfig(model="gemini-2.0-flash")
    custom_llm: LLMConfig = LLMConfig(
        model="ai/gemma3",
        api_base="http://localhost:12434/engines/v1",
        api_key="ignored",
    )

    def __init__(self) -> None:
        super().__init__()
        self.logger_settings.logging_config = LoggerSettings.load_from_yaml()


settings = Settings()
