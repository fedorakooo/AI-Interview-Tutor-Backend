from pydantic_settings import BaseSettings, SettingsConfigDict


class RabbitMQSettings(BaseSettings):
    """RabbitMQ connection settings."""

    port: int = 5672
    host: str = "rabbitmq"
    user: str
    password: str

    timeout: float = 30

    model_config = SettingsConfigDict(env_prefix="RABBITMQ_", env_file=".env", extra="ignore")


class MongoSettings(BaseSettings):
    """MongoDB connection settings."""

    port: int = 27017
    host: str = "mongodb"
    user: str
    password: str
    authSource: str

    db_name: str
    messages_collection_name: str

    @property
    def url(self) -> str:
        return f"mongodb://{self.user}:{self.password}@{self.host}/{self.db_name}"

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
