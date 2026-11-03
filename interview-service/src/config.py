from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class MongoSettings(BaseSettings):
    host: str = "mongodb"
    port: int = 27017
    user: str = "app"
    password: str = "app"
    auth_source: str = "ai_interview"
    db_name: str = "ai_interview"
    cv_analysis_collection_name: str = "cv_analysis"
    interview_events_collection_name: str = "interview_events"
    interview_assessments_collection_name: str = "interview_assessments"
    interview_feedback_collection_name: str = "interview_feedback"
    interview_completion_outbox_collection_name: str = "interview_completion_outbox"
    interview_assessment_reviews_collection_name: str = "interview_assessment_reviews"

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


class RedisSettings(BaseSettings):
    host: str = "redis"
    port: int = 6379
    password: str = "redis"
    user: str = "app"
    decode_responses: bool = True

    model_config = SettingsConfigDict(env_prefix="REDIS_", env_file=".env", extra="ignore")


class RabbitMQSettings(BaseSettings):
    host: str = "rabbitmq"
    port: int = 5672
    user: str = "guest"
    password: str = "guest"
    assessment_completed_queue_name: str = "assessment-completed"

    @property
    def url(self) -> str:
        return f"amqp://{self.user}:{self.password}@{self.host}:{self.port}/"

    model_config = SettingsConfigDict(env_prefix="RABBITMQ_", env_file=".env", extra="ignore")


class UserManagementSettings(BaseSettings):
    url: str = "http://user-management:8000"
    internal_service_token: str = ""
    timeout_seconds: float = 5.0

    model_config = SettingsConfigDict(env_prefix="USER_MANAGEMENT_", env_file=".env", extra="ignore")


class AppSettings(BaseSettings):
    port: int = 8001

    model_config = SettingsConfigDict(env_prefix="INTERVIEW_SERVICE_", env_file=".env", extra="ignore")


class LoggerSettings(BaseSettings):
    logging_config: dict[str, Any] = {}

    @classmethod
    def load_from_yaml(cls, file_path: str = "config.yaml") -> dict[str, Any]:
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

    interview_hello_timeout_seconds: float = 10.0
    internal_service_token: str = Field(default="", validation_alias="INTERNAL_SERVICE_TOKEN")
    interview_evaluator_models: str = Field(default="openai:gpt-4o-mini", validation_alias="INTERVIEW_EVALUATOR_MODELS")
    interview_interviewer_models: str = Field(
        default="openai:gpt-4o-mini", validation_alias="INTERVIEW_INTERVIEWER_MODELS"
    )
    interview_report_models: str = Field(default="openai:gpt-4o-mini", validation_alias="INTERVIEW_REPORT_MODELS")
    interview_spec_models: str = Field(default="openai:gpt-4o-mini", validation_alias="INTERVIEW_SPEC_MODELS")
    interview_feedback_models: str = Field(default="openai:gpt-4o-mini", validation_alias="INTERVIEW_FEEDBACK_MODELS")

    logger_settings: LoggerSettings = LoggerSettings()
    app_settings: AppSettings = AppSettings()
    mongo_settings: MongoSettings = MongoSettings()
    jwt_settings: JWTSettings = JWTSettings()
    redis_settings: RedisSettings = RedisSettings()
    rabbitmq_settings: RabbitMQSettings = RabbitMQSettings()
    user_management_settings: UserManagementSettings = UserManagementSettings()

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
