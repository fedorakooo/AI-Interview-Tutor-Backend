from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    practice_plans_collection_name: str = "practice_plans"
    practice_attempts_collection_name: str = "practice_attempts"
    user_practice_profiles_collection_name: str = "user_practice_profiles"
    cv_analysis_collection_name: str = "cv_analysis"
    interview_sessions_collection_name: str = "interview_sessions"
    cv_user_id_field: str = "user_id"

    @property
    def url(self) -> str:
        return (
            f"mongodb://{self.user}:{self.password}@{self.host}:{self.port}/"
            f"{self.db_name}?authSource={self.auth_source}"
        )

    model_config = SettingsConfigDict(env_prefix="MONGODB_", env_file=".env", extra="ignore")


class RabbitMQSettings(BaseSettings):
    host: str = "rabbitmq"
    port: int = 5672
    user: str = "guest"
    password: str = "guest"
    timeout: float = 60.0
    practice_plan_queue_name: str = "practice-plan-stream"
    practice_plan_dlq_queue_name: str = "practice-plan-stream.dlq"
    interview_completed_queue_name: str = "interview-completed-stream"
    interview_completed_dlq_queue_name: str = "interview-completed-stream.dlq"
    practice_plan_ready_queue_name: str = "practice-plan-ready-stream"

    @property
    def url(self) -> str:
        return f"amqp://{self.user}:{self.password}@{self.host}:{self.port}/"

    model_config = SettingsConfigDict(env_prefix="RABBITMQ_", env_file=".env", extra="ignore")


class JWTSettings(BaseSettings):
    public_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class PracticeSettings(BaseSettings):
    max_exercises_per_plan: int = 15
    default_exercise_count: int = 8
    min_exercise_count: int = 3
    default_daily_plan_quota: int = 3
    llm_temperature: float = 0.5
    grading_temperature: float = 0.2
    grading_pass_threshold: float = 6.0
    llm_timeout_seconds: int = 60
    grading_timeout_seconds: int = 30
    max_generation_retries: int = 2
    supported_exercise_types: list[str] = Field(
        default_factory=lambda: ["mcq_single", "mcq_multi", "open_question", "flashcard"]
    )

    model_config = SettingsConfigDict(env_prefix="PRACTICE_", env_file=".env", extra="ignore")


class LoggerSettings(BaseSettings):
    logging_config: dict[str, Any] = {}

    @classmethod
    def load_from_yaml(cls, file_path: str = "config.yaml") -> dict[str, Any]:
        path = Path(file_path)
        if not path.exists():
            return {}
        with path.open() as file:
            config = yaml.safe_load(file)
            return config.get("logger", {})


class Settings(BaseSettings):
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

    mongo_settings: MongoSettings = Field(default_factory=MongoSettings)
    rabbitmq_settings: RabbitMQSettings = Field(default_factory=RabbitMQSettings)
    jwt_settings: JWTSettings = Field(default_factory=JWTSettings)
    practice_settings: PracticeSettings = Field(default_factory=PracticeSettings)
    logger_settings: LoggerSettings = Field(
        default_factory=lambda: LoggerSettings(logging_config=LoggerSettings.load_from_yaml())
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
    )


settings = Settings()
