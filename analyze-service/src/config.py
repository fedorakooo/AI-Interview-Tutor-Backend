from pydantic_settings import BaseSettings, SettingsConfigDict


class S3Settings(BaseSettings):
    """S3 connection settings."""

    access_key: str
    secret_access_key: str
    endpoint_url: str
    bucket_name: str
    region_name: str

    model_config = SettingsConfigDict(env_prefix="S3_", env_file=".env", extra="ignore")


class RabbitMQSettings(BaseSettings):
    """RabbitMQ connection settings."""

    port: int
    host: str
    user: str
    password: str

    cv_analyzer_queue_name: str = "cv-analyze-stream"
    cv_analysis_results_queue_name: str = "cv-analysis-results"

    timeout: float = 30

    @property
    def url(self) -> str:
        return f"amqp://{self.user}:{self.password}@{self.host}:{self.port}/"

    model_config = SettingsConfigDict(env_prefix="RABBITMQ_", env_file=".env", extra="ignore")


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

    s3_settings: S3Settings = S3Settings()
    rabbitmq_settings: RabbitMQSettings = RabbitMQSettings()
    mongo_settings: MongoSettings = MongoSettings()


settings = Settings()
