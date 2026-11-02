from pydantic_settings import BaseSettings, SettingsConfigDict


class RabbitMQSettings(BaseSettings):
    host: str = "rabbitmq"
    port: int = 5672
    user: str = "guest"
    password: str = "guest"
    interview_completed_queue_name: str = "interview-completed-stream"

    @property
    def url(self) -> str:
        return f"amqp://{self.user}:{self.password}@{self.host}:{self.port}/"

    model_config = SettingsConfigDict(env_prefix="RABBITMQ_", env_file=".env", extra="ignore")
