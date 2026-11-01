from src.api.dependencies.database import get_async_engine
from src.config import settings
from src.infrastructure.postgres import schemas as _schemas  # noqa: F401
from src.infrastructure.postgres.database import Base

engine = get_async_engine()


def require_test_database():
    name = settings.postgres_settings.name
    if not (name.endswith("_test") or name.startswith("test_")):
        raise RuntimeError("Integration tests require a dedicated database named test_* or *_test")


async def init_db():
    require_test_database()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        await conn.commit()


async def drop_db():
    require_test_database()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.commit()
    await engine.dispose()
