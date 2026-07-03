from enum import Enum

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


class S3Settings(BaseSettings):
    """S3 connection settings."""

    access_key: str = "test"
    secret_access_key: str = "test"
    endpoint_url: str = "http://localstack:4566"
    bucket_name: str = "cv-uploads"
    region_name: str = "us-east-1"
    cv_max_upload_bytes: int = 10 * 1024 * 1024

    model_config = SettingsConfigDict(env_prefix="S3_", env_file=".env", extra="ignore")


class RabbitMQSettings(BaseSettings):
    """RabbitMQ connection settings."""

    port: int
    host: str
    user: str
    password: str

    cv_analyzer_queue_name: str = "cv-analyze-stream"
    cv_analyzer_dlq_queue_name: str = "cv-analyze-stream.dlq"
    cv_analysis_results_queue_name: str = "cv-analysis-results"

    timeout: float = 30

    @property
    def url(self) -> str:
        return f"amqp://{self.user}:{self.password}@{self.host}:{self.port}/"

    model_config = SettingsConfigDict(env_prefix="RABBITMQ_", env_file=".env", extra="ignore")


class DoclingSettings(BaseSettings):
    """Docling PDF extraction settings."""

    do_ocr: bool = True
    do_table_structure: bool = True

    model_config = SettingsConfigDict(env_prefix="DOCLING_", env_file=".env", extra="ignore")


class MongoSettings(BaseSettings):
    """MongoDB connection settings."""

    port: int
    host: str
    user: str
    password: str
    auth_source: str = "ai_interview"

    db_name: str
    cv_analysis_collection_name: str

    @property
    def url(self) -> str:
        return (
            f"mongodb://{self.user}:{self.password}@{self.host}:{self.port}/"
            f"{self.db_name}?authSource={self.auth_source}"
        )

    model_config = SettingsConfigDict(env_prefix="MONGODB_", env_file=".env", extra="ignore")


class Settings(BaseSettings):
    """Application settings container."""

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

    analyze_llm_temperature: float | None = Field(default=0.2, validation_alias="ANALYZE_LLM__TEMPERATURE")

    s3_settings: S3Settings = S3Settings()
    rabbitmq_settings: RabbitMQSettings = RabbitMQSettings()
    mongo_settings: MongoSettings = MongoSettings()
    docling_settings: DoclingSettings = DoclingSettings()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
    )


settings = Settings()
