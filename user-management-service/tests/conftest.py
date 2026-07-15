import os
from pathlib import Path

from faker import Faker

_FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


def _fixture_pem(name: str) -> str:
    return (_FIXTURES_DIR / name).read_text()


os.environ.setdefault("POSTGRES_USER", "postgres")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_NAME", "user_management")
os.environ.setdefault("POSTGRES_PASSWORD", "postgres")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("REDIS_PASSWORD", "")
os.environ.setdefault("REDIS_USER", "default")
os.environ.setdefault("REDIS_USER_PASSWORD", "")
os.environ.setdefault("RABBITMQ_HOST", "localhost")
os.environ.setdefault("RABBITMQ_PORT", "5672")
os.environ.setdefault("RABBITMQ_USER", "guest")
os.environ.setdefault("RABBITMQ_PASSWORD", "guest")
os.environ.setdefault("PUBLIC_KEY", _fixture_pem("dev_rsa_public.pem"))
os.environ.setdefault("PRIVATE_KEY", _fixture_pem("dev_rsa_private.pem"))

faker = Faker(locale="ru_RU")
