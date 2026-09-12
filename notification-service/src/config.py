from pydantic_settings import BaseSettings, SettingsConfigDict


class RabbitMQSettings(BaseSettings):
    """RabbitMQ connection settings."""

    port: int = 5672
    host: str = "rabbitmq"
    user: str
    password: str

    reset_password_queue_name: str = "reset-password-stream"
    reset_password_dlq_queue_name: str = "reset-password-stream.dlq"
    email_verify_queue_name: str = "email-verify-stream"
    email_verify_dlq_queue_name: str = "email-verify-stream.dlq"
    notifications_queue_name: str = "notifications-stream"
    notifications_dlq_queue_name: str = "notifications-stream.dlq"
    practice_plan_ready_queue_name: str = "practice-plan-ready-stream"

    timeout: float = 30

    @property
    def url(self) -> str:
        return f"amqp://{self.user}:{self.password}@{self.host}:{self.port}/"

    model_config = SettingsConfigDict(env_prefix="RABBITMQ_", env_file=".env", extra="ignore")


class MongoSettings(BaseSettings):
    """MongoDB connection settings."""

    port: int = 27017
    host: str = "mongodb"
    user: str
    password: str
    auth_source: str

    db_name: str
    messages_collection_name: str

    @property
    def url(self) -> str:
        return (
            f"mongodb://{self.user}:{self.password}@{self.host}:{self.port}/"
            f"{self.db_name}?authSource={self.auth_source}"
        )

    model_config = SettingsConfigDict(env_prefix="MONGODB_", env_file=".env", extra="ignore")


class SESSettings(BaseSettings):
    """AWS SES connection settings."""

    aws_access_key: str
    aws_secret_access_key: str
    aws_region: str
    sender_email: str

    model_config = SettingsConfigDict(env_prefix="SES_", env_file=".env", extra="ignore")


class Settings(BaseSettings):
    """Application settings container."""

    rabbitmq_settings: RabbitMQSettings = RabbitMQSettings()
    mongo_settings: MongoSettings = MongoSettings()
    ses_settings: SESSettings = SESSettings()


settings = Settings()
