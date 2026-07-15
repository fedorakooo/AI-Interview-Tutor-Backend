from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from src.config import settings


async def create_postgres_pool() -> AsyncConnectionPool:
    return AsyncConnectionPool(
        conninfo=settings.postgres_checkpoint_settings.url,
        kwargs={"autocommit": True, "row_factory": dict_row},
        open=False,
    )
